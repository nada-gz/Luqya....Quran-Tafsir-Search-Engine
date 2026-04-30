from database import engine
from sqlmodel import Session
from models import Morphology
import re

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    marks = re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]')
    text = re.sub(marks, '', text)
    # Only normalize Alif-based hamzas to Alif.\n    text = re.sub(r'[إأآٱ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()

q = "ابتلاء"
q_norm = normalize_arabic(q)
print(f"Normalized query: '{q_norm}'")

# strip prefix
for prefix in ['ال', 'بال', 'وال', 'فال', 'كال', 'لل']:
    if q_norm.startswith(prefix):
        q_norm = q_norm[len(prefix):]
        break
print(f"After prefix strip: '{q_norm}'")

with Session(engine) as session:
    morph = session.query(Morphology).filter(Morphology.root == q_norm).first()
    print(f"Exact root match: {morph.root if morph else 'Not found'}")
    
    # Also check the enrichment map
    import json
    with open('enrichment_map.json') as f:
        enrichment_map = json.load(f)
    if morph and morph.root in enrichment_map:
        data = enrichment_map[morph.root]
        print(f"Dominant topic: {data.get('dominant_topic')}")
        print(f"Related themes: {[t['name'] for t in data.get('related_themes', [])]}")
    else:
        print("Root not in enrichment map")
        # Check what keys look like
        matches = [k for k in list(enrichment_map.keys())[:5]]
        print(f"Sample map keys: {matches}")

print("\n--- Checking what 'ابتلاء' looks like vs enrichment map keys ---")
# The enrichment map keys use original Arabic script (with hamza etc)
# Let's check the raw key directly
import json
with open('enrichment_map.json') as f:
    enrichment_map = json.load(f)
# search for a key containing بلو
found = [(k, v.get('dominant_topic')) for k, v in enrichment_map.items() if 'بل' in k]
print(f"Keys with 'بل': {found[:10]}")

# Also check if the DB has the 'بلو' root with original Arabic
with open('enrichment_map.json') as f:
    em = json.load(f)
if 'بلو' in em:
    print(f"\nKey 'بلو' found directly!")
    print(em['بلو'])
