import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
"""
Step 1 of 2 (run while morphology table still exists in quran.db):
Pre-compute norm_to_root + prefix_to_root from the morphology table,
then save to root_lookup.json. After this, the morphology table is
no longer needed at runtime — setup_fts.py will drop it.
"""
import sqlite3
import json
import re
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'quran.db')
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'root_lookup.json')


def normalize_arabic(text):
    if not text:
        return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    text = re.sub(re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]'), '', text)
    text = re.sub(r'[إأآٱءئؤ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()


def main():
    print("Reading morphology table…")
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT text, lemma, root FROM morphology "
        "WHERE root IS NOT NULL AND root != ''"
    ).fetchall()
    conn.close()
    print(f"  {len(rows):,} morphology rows loaded")

    norm_to_root: dict = {}
    for text, lemma, root in rows:
        nt = normalize_arabic(text)
        nl = normalize_arabic(lemma)
        if nt and nt not in norm_to_root:
            norm_to_root[nt] = root
        if nl and nl not in norm_to_root:
            norm_to_root[nl] = root

    prefix_to_root: dict = {}
    for word, root in norm_to_root.items():
        for i in range(4, len(word)):
            pfx = word[:i]
            if pfx not in prefix_to_root:
                prefix_to_root[pfx] = root

    data = {"norm_to_root": norm_to_root, "prefix_to_root": prefix_to_root}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUT) // 1024
    print(f"  norm_to_root : {len(norm_to_root):,} entries")
    print(f"  prefix_to_root: {len(prefix_to_root):,} entries")
    print(f"  Saved → root_lookup.json ({size_kb} KB)")


if __name__ == '__main__':
    main()
