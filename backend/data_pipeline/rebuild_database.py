"""
Rebuilds the complete SQLite FTS5 database (quran.db) from scratch locally.
Downloads Quran and Tafsir text from APIs, completely bypassing Meilisearch.
Applies the saved enrichment_map.json to index thematic metadata into the FTS engine.
"""
import requests
import sqlite3
import re
import json
import time
import os
import sys

# Allow importing from backend parent despite being in data_pipeline
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import engine
from sqlmodel import Session, SQLModel
from models import Surah, Ayah, Tafsir
from sqlalchemy import text

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'quran.db')

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u0654\u0655]', '\u0627', text)
    text = re.sub(re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]'), '', text)
    text = re.sub(r'[\u0625\u0623\u0622\u0671\u0621\u0626\u0624]', '\u0627', text)
    text = re.sub(r'[\u0649]', '\u064a', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'\u0627+', '\u0627', text)
    return text.strip()

def fetch_json(url):
    print(f"Fetching: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    for _ in range(3):
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        time.sleep(1)
    raise Exception(f"Failed to fetch {url}")

def main():
    # ── 1. Load Topic mapping (enrichment_map.json) ──────────────────────────
    base_dir = os.path.dirname(os.path.dirname(__file__))
    enrich_path = os.path.join(base_dir, 'enrichment_map.json')
    try:
        with open(enrich_path, 'r') as f:
            enrichment_map = json.load(f)
        print(f"Loaded enrichment map: {len(enrichment_map)} roots")
    except Exception as e:
        print(f"Error loading enrichment map (make sure it exists): {e}")
        enrichment_map = {}

    roots_path = os.path.join(base_dir, 'root_lookup.json')
    try:
        with open(roots_path, 'r') as f:
            lookup = json.load(f)
            norm_dict = lookup.get('norm_to_root', {})
    except Exception:
        norm_dict = {}

    # ── 2. Download Base Data ────────────────────────────────────────────────
    surah_info = fetch_json("https://raw.githubusercontent.com/fawazahmed0/quran-api/1/info.json")
    quran_data = fetch_json("https://raw.githubusercontent.com/fawazahmed0/quran-api/1/editions/ara-quranuthmanihaf.json")
    
    tafsir_slugs = {
        'moyassar': 'ar-tafsir-muyassar',
        'saadi': 'ar-tafseer-al-saddi',
        'katheer': 'ar-tafsir-ibn-kathir',
        'tabari': 'ar-tafsir-al-tabari'
    }

    # ── 3. Populate Standard Tables (Surah, Ayah, Tafsir) ────────────────────
    print("Initializing Database tables...")
    SQLModel.metadata.create_all(engine)

    print("Clearing old tables...")
    with Session(engine) as session:
        session.execute(text("DELETE FROM tafsir"))
        session.execute(text("DELETE FROM ayah"))
        session.execute(text("DELETE FROM surah"))
        session.execute(text("DROP TABLE IF EXISTS morphology"))
        session.commit()

        print("Populating Surah metadata...")
        surah_map = {}
        for s in surah_info['chapters']:
            surah = Surah(number=s['chapter'], name_arabic=s['arabicname'],
                          name_english=s['englishname'], revelation_type=s['revelation'])
            session.add(surah)
            session.commit()
            surah_map[s['chapter']] = surah.id

        all_ayahs = quran_data['quran']
        print(f"Ingesting {len(all_ayahs)} Ayahs & Tafsirs...")
        
        current_surah = -1
        tafsir_cache = {}
        
        # Prepare FTS metadata cache
        fts_rows = []

        for idx, ayah_raw in enumerate(all_ayahs):
            s_num = ayah_raw['chapter']
            a_num = ayah_raw['verse']
            txt = ayah_raw['text']
            txt_norm = normalize_arabic(txt)
            
            if s_num != current_surah:
                print(f"  Downloading Tafsir for Surah {s_num}...")
                tafsir_cache = {}
                for key, slug in tafsir_slugs.items():
                    try:
                        url = f"https://raw.githubusercontent.com/spa5k/tafsir_api/main/tafsir/{slug}/{s_num}.json"
                        resp = requests.get(url)
                        if resp.status_code == 200:
                            tafsir_cache[key] = {t['ayah']: t['text'] for t in resp.json().get('ayahs', [])}
                        else: tafsir_cache[key] = {}
                    except: tafsir_cache[key] = {}
                current_surah = s_num
                
            new_ayah = Ayah(surah_id=surah_map[s_num], ayah_number=a_num, text_uthmani=txt)
            session.add(new_ayah)
            session.flush()

            for key in tafsir_slugs.keys():
                ext_txt = tafsir_cache.get(key, {}).get(a_num, "")
                if ext_txt:
                    typ = f"simple_{key}" if key in ['moyassar', 'saadi'] else f"advanced_{key}"
                    session.add(Tafsir(ayah_id=new_ayah.id, tafsir_type=typ, text=ext_txt))

            # Resolve themes for this ayah
            words = txt_norm.split()
            ayah_roots = list(set([norm_dict.get(w) for w in words if norm_dict.get(w)]))
            ayah_themes = []
            for r in ayah_roots:
                rdata = enrichment_map.get(r, {})
                dt = rdata.get("dominant_topic")
                if dt: ayah_themes.append(dt)
                ayah_themes.extend([rt["name"] for rt in rdata.get("related_themes", [])])
            
            fts_rows.append((
                new_ayah.id, s_num,
                surah_info['chapters'][s_num-1]['arabicname'],
                a_num, txt, txt_norm,
                ' '.join(ayah_roots), '', ' | '.join(list(set(ayah_themes)))
            ))
            
            if (idx+1) % 500 == 0:
                session.commit()
                
        session.commit()

    # ── 4. Build FTS5 Index ──────────────────────────────────────────────────
    print("Building SQLite FTS5 Engine...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS ayah_fts")
    c.execute("DROP TABLE IF EXISTS ayah_meta")
    c.execute("DROP TABLE IF EXISTS ayah_fts_data")

    c.execute("""
        CREATE TABLE ayah_meta (
            id INTEGER PRIMARY KEY, surah_number INTEGER NOT NULL,
            surah_name TEXT NOT NULL, ayah_number INTEGER NOT NULL,
            text_uthmani TEXT NOT NULL, text_normalized TEXT NOT NULL,
            roots_text TEXT NOT NULL, lemmas_text TEXT NOT NULL,
            themes_text TEXT NOT NULL
        )
    """)
    c.executemany("INSERT INTO ayah_meta VALUES (?,?,?,?,?,?,?,?,?)", fts_rows)
    conn.commit()

    c.execute("""
        CREATE VIRTUAL TABLE ayah_fts USING fts5(
            text_normalized, text_uthmani, themes_text, content='ayah_meta',
            content_rowid='id', tokenize='unicode61 remove_diacritics 1'
        )
    """)
    c.execute("""
        INSERT INTO ayah_fts(rowid, text_normalized, text_uthmani, themes_text)
        SELECT id, text_normalized, text_uthmani, themes_text FROM ayah_meta
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tafsir_cover ON tafsir(ayah_id, tafsir_type)")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    print(f"Full Setup Complete! Database rebuilt successfully at {DB_PATH}.")

if __name__ == '__main__':
    main()
