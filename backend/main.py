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

# Load enrichment map for semantic grouping
import json
import os
try:
    with open(os.path.join(os.path.dirname(__file__), 'enrichment_map.json'), 'r') as f:
        enrichment_map = json.load(f)
except:
    enrichment_map = {}

# Pre-build a normalized-word → root dictionary at startup.
# This maps every normalized text/lemma form in the Quran morphology to its
# linguistic root, enabling O(1) lookups with no tashkeel mismatch.
norm_to_root: dict = {}
try:
    from sqlmodel import Session as _Session
    from models import Morphology as _Morph
    from database import engine as _engine
    with _Session(_engine) as _s:
        for row in _s.query(_Morph).all():
            if row.root:
                nt = normalize_arabic(row.text)
                nl = normalize_arabic(row.lemma)
                if nt and nt not in norm_to_root:
                    norm_to_root[nt] = row.root
                if nl and nl not in norm_to_root:
                    norm_to_root[nl] = row.root
    print(f"[startup] norm_to_root built: {len(norm_to_root)} entries")
    # Also build a prefix index: word_prefix → root for fuzzy masdar matching
    # e.g. 'ابتل' → 'بلو' (because 'ابتلي' is in the dict with root بلو)
    prefix_to_root: dict = {}
    for word, root_val in norm_to_root.items():
        for i in range(4, len(word)):
            pfx = word[:i]
            if pfx not in prefix_to_root:
                prefix_to_root[pfx] = root_val
    print(f"[startup] prefix_to_root built: {len(prefix_to_root)} entries")
except Exception as _e:
    print(f"[startup] norm_to_root build failed: {_e}")
    prefix_to_root: dict = {}

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
    related_themes_payload = []
    
    if mode == "ayah_only":
        search_params['attributesToSearchOn'] = ['text_normalized', 'text_uthmani']
        # For ayah_only, we want strict matching
        search_params['matchingStrategy'] = 'all'
    elif mode == "tafsir_only":
        search_params['attributesToSearchOn'] = [
            'tafsir_simple_moyassar',
            'tafsir_simple_saadi',
            'tafsir_advanced_katheer',
            'tafsir_advanced_tabari'
        ]
        search_params['matchingStrategy'] = 'all'
    elif mode == "semantic_root":
        q_norm = actual_search_query
        # Strip common Arabic prefixes to get to the root concept
        for prefix in ['ال', 'بال', 'وال', 'فال', 'كال', 'لل']:
            if q_norm.startswith(prefix):
                q_norm = q_norm[len(prefix):]
                break
        
        with Session(engine) as session:
            try:
                # O(1) normalized-word → root lookup using the precomputed dict.
                # No SQL needed, no tashkeel mismatch, no false-positives.
                root = norm_to_root.get(q_norm)
                # Fuzzy fallback: if exact form not found (e.g. user typed masdar
                # 'ابتلاء'→'ابتلا' which isn't in Quran text), try prefix match.
                if not root and len(q_norm) >= 4:
                    root = prefix_to_root.get(q_norm[:-1])  # strip last char
                if not root and len(q_norm) >= 5:
                    root = prefix_to_root.get(q_norm[:-2])  # strip last 2 chars
                
                if root:
                    root_explanation = f"Linguistic Root: {root}"
                    
                    if root in enrichment_map:
                        root_data = enrichment_map[root]
                        dom_theme = root_data.get('dominant_topic', '')
                        if dom_theme:
                            root_explanation += f" → {dom_theme}"
                        
                        # FIX 2: DIVERSIFIED RESULTS — collect up to 10 ayahs per
                        # topic across all themes (dominant + siblings), merge &
                        # deduplicate, instead of overwriting the query with one
                        # topic that floods all 50 result slots.
                        all_topics = []
                        if dom_theme:
                            dom_ar = dom_theme.split('(')[0].strip() if '(' in dom_theme else dom_theme
                            all_topics.append({'name': dom_theme, 'ar': dom_ar, 'is_dominant': True})
                        for rtheme in root_data.get('related_themes', []):
                            rname = rtheme['name']
                            rar = rname.split('(')[0].strip() if '(' in rname else rname
                            all_topics.append({'name': rname, 'ar': rar, 'is_dominant': False})
                        
                        LIMIT_PER_TOPIC = 10
                        seen_ids = set()
                        diversified_hits = []
                        
                        for topic in all_topics:
                            sub_res = index.search(topic['ar'], {
                                'attributesToSearchOn': ['themes'],
                                'limit': LIMIT_PER_TOPIC,
                                'matchingStrategy': 'all'
                            })
                            for hit in sub_res.get('hits', []):
                                if hit['id'] not in seen_ids:
                                    seen_ids.add(hit['id'])
                                    hit['_matched_topic'] = topic['name']
                                    diversified_hits.append(hit)
                        
                        # The first topic section is the direct/dominant result,
                        # the rest go into the related themes sidebar
                        if all_topics:
                            dom_topic_name = all_topics[0]['name']
                            direct_hits = [h for h in diversified_hits if h.get('_matched_topic') == dom_topic_name]
                            sidebar_topics_seen = {}
                            for h in diversified_hits:
                                t = h.get('_matched_topic', '')
                                if t != dom_topic_name:
                                    sidebar_topics_seen.setdefault(t, []).append(h)
                            
                            for tname, hits in sidebar_topics_seen.items():
                                related_themes_payload.append({
                                    "theme_name": tname,
                                    "ayahs": hits
                                })
                            
                            # Use diversified hits as the actual_search_query
                            # replacement — we'll bypass the MeiliSearch call below
                            # by pre-populating processed_hits directly.
                            for hit in direct_hits[:50]:
                                hit['explanation'] = root_explanation or "مطابقة دلالية"
                                hit.pop('_matchesPosition', None)
                                hit.pop('_matched_topic', None)
                            
                            return {
                                "query": q,
                                "mode": mode,
                                "processingTimeMs": 0,
                                "count": len(direct_hits),
                                "results": direct_hits[:50],
                                "related_themes": related_themes_payload
                            }
                
                # Fallback: no root found — do a broad thematic text search
                search_params['attributesToSearchOn'] = ['themes', 'text_normalized']
                search_params['matchingStrategy'] = 'last'
            except Exception as e:
                return {"error": True, "message": str(e)}

    # Perform the search
    results = index.search(actual_search_query, search_params)
    
    processed_hits = []
    
    for hit in results.get('hits', []):
        explanation = []
        is_verified_match = False
        
        if mode == "semantic_root":
            # Semantic mode accepts Meilisearch results directly
            is_verified_match = True
            if root_explanation: explanation.append(root_explanation)
            
            # Find which themes matched
            found_themes = []
            for theme in hit.get('themes', []):
                # Check for match in theme name
                theme_norm = normalize_arabic(theme)
                if normalize_arabic(q) in theme_norm or any(s in theme_norm for s in actual_search_query.split()):
                    found_themes.append(theme.split('|')[-1].strip())
            
            if found_themes:
                explanation.append(f"Thematic Match: {', '.join(list(set(found_themes))[:2])}")
        else:
            # STRICT match for ayah_only and tafsir_only as requested
            q_norm = normalize_arabic(q)
            expl_set = set()
            for attr in searchable_attrs_in_mode(mode):
                attr_text = hit.get(attr, "")
                if not attr_text: continue
                
                # STRICT match: Require word boundaries for ayah_only
                text_norm = normalize_arabic(attr_text)
                if mode == "ayah_only":
                    # Use boundary markers to ensure exact word match
                    pattern = r'(^|\s)' + re.escape(q_norm) + r'(\s|$)'
                    if re.search(pattern, text_norm):
                        is_verified_match = True
                else:
                    # Substring match for tafsir is generally preferred but can be tuned
                    if q_norm in text_norm:
                        is_verified_match = True
                
                if is_verified_match:
                    if attr in ['text_uthmani', 'text_normalized']:
                        expl_set.add("تم العثور في نص الآية")
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
            hit['explanation'] = " | ".join(explanation) if explanation else ("مطابقة عامة" if mode=="semantic_root" else "مطابقة مباشرة")
            if '_matchesPosition' in hit: del hit['_matchesPosition']
            processed_hits.append(hit)

    # Custom Sorting for Option 1 (ayah_only) as requested
    if mode == "ayah_only":
        q_norm = normalize_arabic(q)
        starts_with, contains = [], []
        for h in processed_hits:
            if h.get('text_normalized', "").startswith(q_norm):
                starts_with.append(h)
            else:
                contains.append(h)
        starts_with.sort(key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))
        contains.sort(key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))
        processed_hits = starts_with + contains
    elif mode == "tafsir_only":
        processed_hits.sort(key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))
        
    return {
        "query": q,
        "mode": mode,
        "processingTimeMs": results.get('processingTimeMs'),
        "count": len(processed_hits),
        "results": processed_hits,
        "related_themes": related_themes_payload
    }

def searchable_attrs_in_mode(mode):
    if mode == "ayah_only":
        return ['text_uthmani', 'text_normalized']
    elif mode == "tafsir_only":
        return ['tafsir_simple_moyassar', 'tafsir_simple_saadi', 'tafsir_advanced_katheer', 'tafsir_advanced_tabari']
    elif mode == "semantic_root":
        return ['roots', 'themes', 'lemmas']
    return []
