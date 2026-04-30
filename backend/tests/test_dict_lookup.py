# Test dict lookup in isolation
import sys
sys.path.insert(0, '.')

# Reproduce exactly what main.py does at startup
import re
def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    text = re.sub(re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]'), '', text)
    # Only normalize Alif-based hamzas to Alif.\n    text = re.sub(r'[إأآٱ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()

from sqlmodel import Session
from models import Morphology
from database import engine

norm_to_root = {}
with Session(engine) as s:
    for row in s.query(Morphology).all():
        if row.root:
            nt = normalize_arabic(row.text)
            nl = normalize_arabic(row.lemma)
            if nt and nt not in norm_to_root:
                norm_to_root[nt] = row.root
            if nl and nl not in norm_to_root:
                norm_to_root[nl] = row.root

print(f"Dict size: {len(norm_to_root)}")

# Test lookup
q = "ابتلاء"
q_norm = normalize_arabic(q)
for prefix in ['ال', 'بال', 'وال', 'فال', 'كال', 'لل']:
    if q_norm.startswith(prefix):
        q_norm = q_norm[len(prefix):]
        break

print(f"q_norm after prefix strip: '{q_norm}'")
root = norm_to_root.get(q_norm)
print(f"Root found: {root}")

# Also check بلا and بلو
print(f"'بلا' in dict: {norm_to_root.get('بلا')}")
print(f"'بلو' in dict: {norm_to_root.get('بلو')}")
print(f"'ابتلي' in dict: {norm_to_root.get('ابتلي')}")
