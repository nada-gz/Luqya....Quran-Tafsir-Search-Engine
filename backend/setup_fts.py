"""
Step 2 of 2 (run ONCE while Meilisearch is still running):
- Exports themes/roots/lemmas from Meilisearch for all 6236 ayahs
- Creates ayah_meta (tiny metadata table) and ayah_fts FTS5 virtual table
- Adds a covering index on tafsir(ayah_id, tafsir_type) for fast lookups
- Drops the morphology table (no longer needed — root_lookup.json has data)
- VACUUMs the DB to reclaim space (~55 MB final)
After this completes, Meilisearch is no longer needed.
"""
import meilisearch
import sqlite3
import re
import os

DB = os.path.join(os.path.dirname(__file__), 'quran.db')
MEILI_URL = 'http://127.0.0.1:7700'
MEILI_KEY = 'quran_search_master_key'


def normalize_arabic(text):
    if not text:
        return ""
    text = re.sub(r'[\u0654\u0655]', '\u0627', text)
    text = re.sub(re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]'), '', text)
    text = re.sub(r'[\u0625\u0623\u0622\u0671\u0621\u0626\u0624]', '\u0627', text)
    text = re.sub(r'[\u0649]', '\u064a', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'\u0627+', '\u0627', text)
    return text.strip()


def fetch_all_meili_docs():
    client = meilisearch.Client(MEILI_URL, MEILI_KEY)
    all_docs = []
    offset = 0
    batch = 1000
    while True:
        res = client.index('quran').get_documents({'limit': batch, 'offset': offset})
        docs = res.results
        all_docs.extend(docs)
        print(f"  fetched {len(all_docs)} / {res.total} ...")
        if len(docs) < batch:
            break
        offset += batch
    return all_docs


def main():
    # 1. Fetch themes/roots/lemmas from Meilisearch
    print("Exporting Meilisearch documents...")
    all_docs = fetch_all_meili_docs()
    print(f"  Total documents: {len(all_docs)}")

    meili_meta: dict = {}
    for doc in all_docs:
        d = doc if isinstance(doc, dict) else dict(doc)
        aid = d.get('id')
        if aid is not None:
            meili_meta[aid] = {
                'themes': d.get('themes') or [],
                'roots':  d.get('roots')  or [],
                'lemmas': d.get('lemmas') or [],
            }

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # NOTE: FTS5 creates shadow tables named {fts_name}_data, {fts_name}_idx, etc.
    # So we CANNOT name our content table 'ayah_fts_data' (would collide with
    # the FTS5 shadow table). We use 'ayah_meta' instead.
    print("Dropping existing FTS artifacts...")
    c.execute("DROP TABLE IF EXISTS ayah_fts")   # virtual table first
    c.execute("DROP TABLE IF EXISTS ayah_meta")  # our content table
    c.execute("DROP TABLE IF EXISTS ayah_fts_data")   # orphan from first failed run

    # 2. Create the denormalized metadata table (NO tafsir — already in tafsir table)
    c.execute("""
        CREATE TABLE ayah_meta (
            id              INTEGER PRIMARY KEY,
            surah_number    INTEGER  NOT NULL,
            surah_name      TEXT     NOT NULL DEFAULT '',
            ayah_number     INTEGER  NOT NULL,
            text_uthmani    TEXT     NOT NULL DEFAULT '',
            text_normalized TEXT     NOT NULL DEFAULT '',
            roots_text      TEXT     NOT NULL DEFAULT '',
            lemmas_text     TEXT     NOT NULL DEFAULT '',
            themes_text     TEXT     NOT NULL DEFAULT ''
        )
    """)

    # 3. Populate from existing DB + Meilisearch metadata
    source_rows = c.execute("""
        SELECT a.id, s.number, s.name_arabic, a.ayah_number, a.text_uthmani
        FROM ayah a
        JOIN surah s ON a.surah_id = s.id
        ORDER BY s.number, a.ayah_number
    """).fetchall()

    insert_rows = []
    for ayah_id, surah_num, surah_name, ayah_num, text_uthmani in source_rows:
        text_normalized = normalize_arabic(text_uthmani or '')
        md = meili_meta.get(ayah_id, {})
        themes_text = ' | '.join(md.get('themes', []))
        roots_text  = ' '.join(md.get('roots', []))
        lemmas_text = ' '.join(md.get('lemmas', []))
        insert_rows.append((
            ayah_id, surah_num, surah_name, ayah_num,
            text_uthmani or '', text_normalized,
            roots_text, lemmas_text, themes_text
        ))

    c.executemany("INSERT OR REPLACE INTO ayah_meta VALUES (?,?,?,?,?,?,?,?,?)", insert_rows)
    conn.commit()
    print(f"  Inserted {len(insert_rows)} rows into ayah_meta")

    # 4. Create FTS5 virtual table (content table backed by ayah_meta)
    # Indexes only text + themes — tafsir is searched separately via LIKE.
    # 'remove_diacritics 1' strips Arabic tashkeel for diacritic-insensitive search.
    c.execute("""
        CREATE VIRTUAL TABLE ayah_fts USING fts5(
            text_normalized,
            text_uthmani,
            themes_text,
            content='ayah_meta',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 1'
        )
    """)
    c.execute("""
        INSERT INTO ayah_fts(rowid, text_normalized, text_uthmani, themes_text)
        SELECT id, text_normalized, text_uthmani, themes_text FROM ayah_meta
    """)
    conn.commit()
    print("  FTS5 index created and populated")

    # 5. Add covering index on tafsir for fast per-ayah lookups
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_tafsir_cover "
        "ON tafsir(ayah_id, tafsir_type)"
    )
    conn.commit()
    print("  Index on tafsir(ayah_id, tafsir_type) created")

    # 6. Drop morphology table (now baked into root_lookup.json)
    c.execute("DROP TABLE IF EXISTS morphology")
    conn.commit()
    print("  morphology table dropped")

    # 7. VACUUM to reclaim disk space
    print("  VACUUMing database (may take 10-30 seconds)...")
    conn.execute("VACUUM")
    conn.commit()
    conn.close()

    size_mb = os.path.getsize(DB) / 1_048_576
    print(f"\nDone! quran.db is now {size_mb:.1f} MB")
    print("Meilisearch is no longer needed.")


if __name__ == '__main__':
    main()
