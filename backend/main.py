import meilisearch
from typing import Optional
import re
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from database import engine
from models import Morphology

def normalize_arabic(text):
    if not text: return ""
    # Strip Tashkeel
    tashkeel = re.compile(r'[\u064B-\u065F\u0670]')
    text = re.sub(tashkeel, '', text)
    # Normalize Alif variants (including Alif Wasla)
    text = re.sub(r'[إأآٱ]', 'ا', text)
    # Normalize Hamza variants
    text = re.sub(r'[ؤ]', 'و', text)
    text = re.sub(r'[ئ]', 'ي', text)
    return text

app = FastAPI(title="Smart Quran & Tafsir Search Engine", description="Dataset-driven Semantic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')

@app.get("/")
def read_root():
    return {"status": "active", "engine": "MeiliSearch + Quranic Corpus"}

@app.get("/api/search")
def search(
    q: str = Query(..., description="The search query"), 
    mode: str = Query("ayah_only", description="Mode: ayah_only, tafsir_only, semantic_root"),
    surah: Optional[int] = None):
    
    index = search_client.index('quran')
    
    search_params = {
        'showMatchesPosition': True,
        'limit': 50,
        'matchingStrategy': 'all'
    }
    
    if surah:
        search_params['filter'] = [f'surah_number = {surah}']
        
    actual_search_query = normalize_arabic(q)
    root_explanation = None
    
    if mode == "ayah_only":
        search_params['attributesToSearchOn'] = ['text_normalized', 'text_uthmani']
    elif mode == "tafsir_only":
        search_params['attributesToSearchOn'] = [
            'tafsir_simple_moyassar',
            'tafsir_simple_saadi',
            'tafsir_advanced_katheer',
            'tafsir_advanced_tabari'
        ]
    elif mode == "semantic_root":
        # Look up root from the linguistic dataset
        q_norm = actual_search_query
        # Small tweak: remove common Arabic articles for root lookup
        if q_norm.startswith('ال'): q_norm = q_norm[2:]
        if q_norm.startswith('بال'): q_norm = q_norm[3:]
        if q_norm.startswith('وال'): q_norm = q_norm[3:]
        if q_norm.startswith('فال'): q_norm = q_norm[3:]
        
        with Session(engine) as session:
            try:
                # We try to match the root exactly first, or perform a LIKE on the lemma/text
                morph = session.query(Morphology).filter(
                    (Morphology.root == q_norm) | 
                    (Morphology.lemma.like(f"%{q_norm}%")) | 
                    (Morphology.text.like(f"%{q_norm}%"))
                ).first()
                if not morph or not morph.root:
                    return {
                        "error": True,
                        "message": f"Could not find a linguistic root for '{q}' in the Quran. Try searching by Ayah or Tafsir instead."
                    }
                actual_search_query = morph.root
                root_explanation = f"Categorized under Linguistic Root: {actual_search_query}"
                search_params['attributesToSearchOn'] = ['roots']
            except Exception as e:
                return {"error": True, "message": str(e)}

    # Perform the search
    results = index.search(actual_search_query, search_params)
    
    processed_hits = []
    
    for hit in results.get('hits', []):
        matches = hit.get('_matchesPosition', {})
        explanation = []
        
        # Determine which attributes were searched for based on mode
        searched_attrs = []
        if mode == "ayah_only":
            searched_attrs = ['text_uthmani', 'text_normalized']
        elif mode == "tafsir_only":
            searched_attrs = ['tafsir_simple_moyassar', 'tafsir_simple_saadi', 'tafsir_advanced_katheer', 'tafsir_advanced_tabari']
        elif mode == "semantic_root":
            searched_attrs = ['roots']

        if root_explanation and mode == "semantic_root":
            explanation.append(root_explanation)
        else:
            for attr in matches.keys():
                # ONLY add to explanation if the attribute was part of the intended search mode
                if attr in searched_attrs:
                    if attr in ['text_uthmani', 'text_normalized']:
                        explanation.append("keyword found directly in the Ayah text")
                    elif attr.startswith('tafsir_'):
                        clean_name = attr.replace('tafsir_', '').replace('_', ' ').title()
                        explanation.append(f"keyword found in {clean_name} Tafsir")
                
        hit['explanation'] = " | ".join(explanation) if explanation else "matched based on selected focus"
        
        if '_matchesPosition' in hit:
            del hit['_matchesPosition']
            
        processed_hits.append(hit)
        
    return {
        "query": q,
        "mode": mode,
        "processingTimeMs": results.get('processingTimeMs'),
        "estimatedTotalHits": results.get('estimatedTotalHits'),
        "engine": "MeiliSearch",
        "semantic_root_used": actual_search_query if mode == "semantic_root" else None,
        "results": processed_hits
    }
