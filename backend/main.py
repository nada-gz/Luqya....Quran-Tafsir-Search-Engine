"""
Luqya | لُقْيَا  — Quranic Search API
Backed entirely by SQLite FTS5. No Meilisearch required.
Search modes:
  ayah_only    — strict word-boundary match in ayah text
  tafsir_only  — substring match across all four tafsir texts
  semantic_root — root/taxonomy-driven diversified thematic results
"""
import re
import json
import os
import sqlite3
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


# ── Arabic normalization ──────────────────────────────────────────────────────
def normalize_arabic(text, aggressive=False):
    if not text:
        return ""
    # 1. Strip vowels/marks EXCEPT the Hamza marks (0654, 0655)
    # This brings the Alif and its Hamza mark together even if vowels were between them
    pre_marks = re.compile(r'[\u0610-\u061A\u064B-\u0652\u0656-\u065F\u06D6-\u06ED]')
    text = re.sub(pre_marks, '', text)
    
    # 2. Map Uthmani-style carrier+Hamza mark to standard characters
    # ا + Hamza Above -> أ, ا + Hamza Below -> إ, ا + Madda -> آ
    text = text.replace('\u0627\u0654', 'أ').replace('\u0627\u0655', 'إ').replace('\u0627\u0653', 'آ')
    # و + Hamza Above -> ؤ
    text = text.replace('\u0648\u0654', 'ؤ')
    # ى / ي + Hamza Above -> ئ
    text = text.replace('\u0649\u0654', 'ئ').replace('\u064A\u0654', 'ئ')
    
    # 3. Handle standalone/floating Hamza marks (fallback)
    text = text.replace('\u0654', 'أ').replace('\u0655', 'إ')

    # 4. Strip any remaining marks (like Madda \u0653 if not on Alif)
    post_marks = re.compile(r'[\u0653]')
    text = re.sub(post_marks, '', text)
    if aggressive:
        # For root-finding: Merge ALL hamzas into Alif
        text = re.sub(r'[إأآٱءئؤ]', 'ا', text)
        # For root-finding: Merge Alif Maqsura and Ya
        text = re.sub(r'[ى]', 'ي', text)
    else:
        # Ultimate Precise: Keep 'ى' and 'ي' distinct.
        # Keep all Hamzas distinct.
        pass
    
    text = re.sub(r'[\u0640]', '', text)
    
    # Strip dagger alif (\u0670) as it is a mark, not a letter
    text = re.sub(r'\u0670', '', text)

    # Silent Alif Rule: Treat 'وا' at the end of a word as 'و' 
    # to allow 'قالو' to match 'قالوا' even with strict boundaries.
    text = re.sub(r'وا($|\s)', r'و\1', text)
    
    # Standard orthography exceptions
    text = re.sub(r'\bهاذا\b', 'هذا', text)
    text = re.sub(r'\bهاذه\b', 'هذه', text)
    text = re.sub(r'\bذالك\b', 'ذلك', text)
    text = re.sub(r'\bكذالك\b', 'كذلك', text)
    text = re.sub(r'\bذالكم\b', 'ذلكم', text)
    text = re.sub(r'\bرحمان\b', 'رحمن', text)
    text = re.sub(r'\bالرحمان\b', 'الرحمن', text)
    text = re.sub(r'\bالاه\b', 'اله', text)
    text = re.sub(r'\bلاكن\b', 'لكن', text)
    text = re.sub(r'\bطاها\b', 'طه', text)

    # Uthmani Waw-Alif exceptions
    text = text.replace('الصلوة', 'الصلاة')
    text = text.replace('الزكوة', 'الزكاة')
    text = text.replace('الحيوة', 'الحياة')
    text = text.replace('النجوة', 'النجاة')
    text = text.replace('منوة', 'مناة')
    text = text.replace('الغدوة', 'الغداة')
    # Bare words
    text = text.replace('صلوة', 'صلاة')
    text = text.replace('زكوة', 'زكاة')
    text = text.replace('حيوة', 'حياة')

    text = re.sub(r'[ٱ]', 'ا', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()


# ── Paths ────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(__file__)
FTS_DB = os.path.join(_BASE, 'quran.db')

# ── Load enrichment map (root → dominant topic + siblings) ───────────────────
try:
    with open(os.path.join(_BASE, 'enrichment_map.json'), 'r') as _f:
        enrichment_map: dict = json.load(_f)
except Exception:
    enrichment_map = {}

# ── Load pre-computed root lookup (replaces morphology DB table) ──────────────
# norm_to_root  : normalized word form → linguistic root  (exact, O(1))
# prefix_to_root: word prefix          → linguistic root  (fallback for masdars)
norm_to_root: dict = {}
prefix_to_root: dict = {}
try:
    with open(os.path.join(_BASE, 'root_lookup.json'), 'r') as _f:
        _rl = json.load(_f)
        norm_to_root   = _rl.get('norm_to_root', {})
        prefix_to_root = _rl.get('prefix_to_root', {})
    print(f"[startup] root_lookup loaded: {len(norm_to_root):,} words, "
          f"{len(prefix_to_root):,} prefixes")
except Exception as _e:
    print(f"[startup] root_lookup.json not found or corrupt: {_e}")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Luqya | لُقْيَا Quran Search",
    description="Dataset-driven semantic Quranic search — SQLite FTS5 powered"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SQLite helpers ────────────────────────────────────────────────────────────

# The SELECT clause used by every search path — joins ayah_meta with the
# existing tafsir table (4 correlated sub-selects, fast with the covering index
# created by setup_fts.py).
_FULL_SELECT = """
    SELECT
        m.id,
        m.surah_number,
        m.surah_name,
        m.ayah_number,
        m.text_uthmani,
        m.text_normalized,
        m.roots_text,
        m.lemmas_text,
        m.themes_text,
        (SELECT text FROM tafsir WHERE ayah_id = m.id AND tafsir_type = 'simple_moyassar'  LIMIT 1) AS tafsir_simple_moyassar,
        (SELECT text FROM tafsir WHERE ayah_id = m.id AND tafsir_type = 'simple_saadi'     LIMIT 1) AS tafsir_simple_saadi,
        (SELECT text FROM tafsir WHERE ayah_id = m.id AND tafsir_type = 'advanced_katheer' LIMIT 1) AS tafsir_advanced_katheer,
        (SELECT text FROM tafsir WHERE ayah_id = m.id AND tafsir_type = 'advanced_tabari'  LIMIT 1) AS tafsir_advanced_tabari
"""


def _conn() -> sqlite3.Connection:
    # Use read-only mode for stability on platforms like Hugging Face
    c = sqlite3.connect(f"file:{FTS_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _row_to_hit(row) -> dict:
    """Convert a sqlite3.Row to a dict that matches the old Meilisearch hit shape."""
    d = dict(row)
    themes_text = d.pop('themes_text', '') or ''
    d['themes'] = [t.strip() for t in themes_text.split(' | ') if t.strip()]
    d['roots']  = (d.pop('roots_text',  '') or '').split()
    d['lemmas'] = (d.pop('lemmas_text', '') or '').split()
    return d


def fts_search(query: str, cols: list, limit: int = 200, surah: int = None) -> list:
    """
    Full-text search via SQLite FTS5 (ayah text + themes only).
    cols — list of FTS5 column names to restrict search to.
    Returns a list of hit dicts identical in shape to the old Meilisearch hits.
    """
    safe_q = (query or '').strip().replace('"', '""')
    if not safe_q:
        return []

    col_spec = ('{' + ' '.join(cols) + '}') if len(cols) > 1 else cols[0]
    fts_expr = f'{col_spec}: "{safe_q}"'

    params: list = [fts_expr]
    surah_clause = ''
    if surah:
        surah_clause = 'AND m.surah_number = ?'
        params.append(surah)
    params.append(limit)

    sql = f"""
        {_FULL_SELECT}
        FROM ayah_fts f
        JOIN ayah_meta m ON f.rowid = m.id
        WHERE ayah_fts MATCH ?
        {surah_clause}
        ORDER BY rank
        LIMIT ?
    """
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print(f"[fts_search] error: {e}  expr: {fts_expr}")
        rows = []
    finally:
        conn.close()
    return [_row_to_hit(r) for r in rows]


def text_search(query: str, cols: list, limit: int = 200, surah: int = None) -> list:
    """
    Substring search for explicit text matching (ayah or tafsir).
    Uses LIKE on the specified columns.
    """
    safe_q = (query or '').strip()
    if not safe_q:
        return []

    like_val = f'%{safe_q}%'
    params: list = []
    
    # Build OR clauses for each column
    or_clauses = [f"{c} LIKE ?" for c in cols]
    params.extend([like_val] * len(cols))
    
    where_sql = " OR ".join(or_clauses)
    if surah:
        where_sql = f"({where_sql}) AND m.surah_number = ?"
        params.append(surah)
    else:
        where_sql = f"({where_sql})"

    params.append(limit)

    # Note: tafsir_ columns are handled by joining the tafsir table
    if any(c.startswith('tafsir_') for c in cols):
        sql = f"""
            {_FULL_SELECT}
            FROM (
                SELECT DISTINCT ayah_id FROM tafsir WHERE text LIKE ?
            ) t_match
            JOIN ayah_meta m ON m.id = t_match.ayah_id
            WHERE {"m.surah_number = ?" if surah else "1=1"}
            ORDER BY m.surah_number, m.ayah_number
            LIMIT ?
        """
        # Overwrite params for tafsir since the logic is simpler
        params = [like_val]
        if surah:
            params.append(surah)
        params.append(limit)
    else:
        sql = f"""
            {_FULL_SELECT}
            FROM ayah_meta m
            WHERE {where_sql}
            ORDER BY m.surah_number, m.ayah_number
            LIMIT ?
        """

    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print(f"[text_search] error: {e}")
        rows = []
    finally:
        conn.close()
    return [_row_to_hit(r) for r in rows]

def tafsir_search(query: str, limit: int = 200, surah: int = None) -> list:
    return text_search(query, ['tafsir_mock'], limit, surah)


def searchable_attrs_in_mode(mode: str) -> list:
    if mode == "ayah_only":
        return ['text_uthmani', 'text_normalized']
    if mode == "tafsir_only":
        return ['tafsir_simple_moyassar', 'tafsir_simple_saadi',
                'tafsir_advanced_katheer', 'tafsir_advanced_tabari']
    if mode == "semantic_root":
        return ['roots', 'themes', 'lemmas']
    return []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "active", "engine": "SQLite FTS5 + Quranic Corpus"}


@app.get("/api/search")
def search(
    q: str = Query(..., description="The search query"),
    mode: str = Query("ayah_only", description="ayah_only | tafsir_only | semantic_root"),
    surah: Optional[int] = None,
):
    actual_search_query = normalize_arabic(q)
    root_explanation: Optional[str] = None
    related_themes_payload: list = []

    # ── Semantic root mode ────────────────────────────────────────────────────
    if mode == "semantic_root":
        # Use aggressive normalization for root finding
        q_norm = normalize_arabic(q, aggressive=True)
        # Strip common Arabic definite-article / preposition prefixes
        for prefix in ['ال', 'بال', 'وال', 'فال', 'كال', 'لل']:
            if q_norm.startswith(prefix):
                q_norm = q_norm[len(prefix):]
                break

        try:
            # O(1) exact lookup; fallback to prefix strip for masdar forms
            # (e.g. 'ابتلاء'→'ابتلا' not in dict, but prefix 'ابتل' points to بلو)
            root = norm_to_root.get(q_norm)
            if not root and len(q_norm) >= 4:
                root = prefix_to_root.get(q_norm[:-1])
            if not root and len(q_norm) >= 5:
                root = prefix_to_root.get(q_norm[:-2])

            if root and root in enrichment_map:
                root_data = enrichment_map[root]
                dom_theme = root_data.get('dominant_topic', '')
                root_explanation = f"Linguistic Root: {root}"
                if dom_theme:
                    root_explanation += f" \u2192 {dom_theme}"

                # Collect dominant topic + all sibling topics
                all_topics: list = []
                if dom_theme:
                    dom_ar = dom_theme.split('(')[0].strip() if '(' in dom_theme else dom_theme
                    all_topics.append({'name': dom_theme, 'ar': dom_ar})
                for rtheme in root_data.get('related_themes', []):
                    rname = rtheme['name']
                    rar = rname.split('(')[0].strip() if '(' in rname else rname
                    all_topics.append({'name': rname, 'ar': rar})

                # Fetch up to 10 ayahs per topic, deduplicate across topics
                LIMIT_PER_TOPIC = 10
                seen_ids: set = set()
                diversified_hits: list = []

                for topic in all_topics:
                    sub_hits = fts_search(topic['ar'], ['themes_text'], limit=LIMIT_PER_TOPIC)
                    for hit in sub_hits:
                        if hit['id'] not in seen_ids:
                            seen_ids.add(hit['id'])
                            hit['_matched_topic'] = topic['name']
                            diversified_hits.append(hit)

                if all_topics:
                    dom_topic_name = all_topics[0]['name']
                    direct_hits = [h for h in diversified_hits
                                   if h.get('_matched_topic') == dom_topic_name]
                    sidebar: dict = {}
                    for h in diversified_hits:
                        t = h.get('_matched_topic', '')
                        if t != dom_topic_name:
                            sidebar.setdefault(t, []).append(h)

                    for tname, hits in sidebar.items():
                        related_themes_payload.append({"theme_name": tname, "ayahs": hits})

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
                        "related_themes": related_themes_payload,
                    }

            # Fallback: no root found → broad themes + ayah text search
            raw_hits = fts_search(actual_search_query, ['themes_text', 'text_normalized'],
                                  limit=200, surah=surah)

        except Exception as e:
            return {"error": True, "message": str(e)}

    # ── Ayah-only mode ────────────────────────────────────────────────────────
    elif mode == "ayah_only":
        raw_hits = text_search(actual_search_query, ['text_normalized', 'text_uthmani'],
                               limit=200, surah=surah)

    # ── Tafsir-only mode ──────────────────────────────────────────────────────
    elif mode == "tafsir_only":
        raw_hits = tafsir_search(actual_search_query, limit=200, surah=surah)

    else:
        raw_hits = []

    # ── Post-process: verify matches + build explanation strings ──────────────
    processed_hits: list = []
    q_norm_display = normalize_arabic(q)

    for hit in raw_hits:
        explanation: list = []
        is_verified_match = False

        if mode == "semantic_root":
            # Fallback path — accept FTS5 results as-is
            is_verified_match = True
            if root_explanation:
                explanation.append(root_explanation)
            found_themes = []
            for theme in hit.get('themes', []):
                theme_norm = normalize_arabic(theme)
                if (q_norm_display in theme_norm or
                        any(s in theme_norm for s in actual_search_query.split())):
                    found_themes.append(theme.split('|')[-1].strip())
            if found_themes:
                explanation.append(f"Thematic Match: {', '.join(list(set(found_themes))[:2])}")
        else:
            expl_set: set = set()
            for attr in searchable_attrs_in_mode(mode):
                attr_text = hit.get(attr, '') or ''
                if not attr_text:
                    continue
                text_norm = normalize_arabic(attr_text)
                if mode == "ayah_only":
                    # Super Precise Exact word match: starts with query and followed by space/end of string
                    pattern = r'(^|\s)' + re.escape(q_norm_display) + r'($|\s)'
                    if re.search(pattern, text_norm):
                        is_verified_match = True
                else:  # tafsir_only
                    pattern = r'(^|\s)' + re.escape(q_norm_display)
                    if re.search(pattern, text_norm):
                        is_verified_match = True
                if is_verified_match:
                    if attr in ('text_uthmani', 'text_normalized'):
                        expl_set.add("تم العثور في نص الآية")
                    elif attr.startswith('tafsir_'):
                        tafsir_map = {
                            'moyassar': 'الميسر', 'saadi': 'السعدي',
                            'katheer': 'ابن كثير', 'tabari': 'الطبري',
                        }
                        src = attr.replace('tafsir_simple_', '').replace('tafsir_advanced_', '')
                        expl_set.add(f"وجد في تفسير {tafsir_map.get(src, src.title())}")
            explanation = list(expl_set)

        if is_verified_match:
            hit['explanation'] = (" | ".join(explanation) if explanation
                                  else ("مطابقة عامة" if mode == "semantic_root"
                                        else "مطابقة مباشرة"))
            hit.pop('_matchesPosition', None)
            processed_hits.append(hit)

    # ── Custom sorting ────────────────────────────────────────────────────────
    if mode == "ayah_only":
        starts = [h for h in processed_hits
                  if h.get('text_normalized', '').startswith(q_norm_display)]
        rest   = [h for h in processed_hits
                  if not h.get('text_normalized', '').startswith(q_norm_display)]
        starts.sort(key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))
        rest.sort(  key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))
        processed_hits = starts + rest
    elif mode == "tafsir_only":
        processed_hits.sort(key=lambda x: (x.get('surah_number', 0), x.get('ayah_number', 0)))

    return {
        "query": q,
        "mode": mode,
        "processingTimeMs": 0,
        "count": len(processed_hits),
        "results": processed_hits[:50],
        "related_themes": related_themes_payload,
    }
