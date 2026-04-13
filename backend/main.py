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
    # Replace hamza-above and hamza-below marks with Alif to preserve the sound seat
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    # Strip all Quranic marks, Tashkeel, and punctuation
    marks = re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]')
    text = re.sub(marks, '', text)
    # Normalize Alif and hamza variants to a plain Alif
    text = re.sub(r'[إأآٱءئؤ]', 'ا', text)
    # Standardize YEH variants
    text = re.sub(r'[ى]', 'ي', text)
    # Strip Tatweel
    text = re.sub(r'[\u0640]', '', text)
    # Collapse duplicate Alifs
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()

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
        is_verified_match = False
        
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
            is_verified_match = True
        else:
            expl_set = set()
            for attr in searchable_attrs_in_mode(mode):
                attr_text = hit.get(attr, "")
                if not attr_text: continue
                
                # Strict substring check in normalized text
                if actual_search_query in normalize_arabic(attr_text):
                    is_verified_match = True
                    if attr in ['text_uthmani', 'text_normalized']:
                        expl_set.add("keyword found directly in the Ayah text")
                    elif attr.startswith('tafsir_'):
                        tafsir_map = {
                            'moyassar': 'الميسر',
                            'saadi': 'السعدي',
                            'katheer': 'ابن كثير',
                            'tabari': 'الطبري'
                        }
                        source = attr.replace('tafsir_simple_', '').replace('tafsir_advanced_', '')
                        name = tafsir_map.get(source, source.title())
                        expl_set.add(f"وجد في تفسير {name}")
            explanation = list(expl_set)
                
        if is_verified_match:
            hit['explanation'] = " | ".join(explanation) if explanation else "matched based on selected focus"
            if '_matchesPosition' in hit:
                del hit['_matchesPosition']
            processed_hits.append(hit)
        
    return {
        "query": q,
        "mode": mode,
        "processingTimeMs": results.get('processingTimeMs'),
        "count": len(processed_hits),
        "results": processed_hits
    }

def searchable_attrs_in_mode(mode):
    if mode == "ayah_only":
        return ['text_uthmani', 'text_normalized']
    elif mode == "tafsir_only":
        return ['tafsir_simple_moyassar', 'tafsir_simple_saadi', 'tafsir_advanced_katheer', 'tafsir_advanced_tabari']
    elif mode == "semantic_root":
        return ['roots']
    return []
