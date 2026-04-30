from database import engine
from sqlmodel import Session
from models import Morphology
import re, json

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    text = re.sub(re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]'), '', text)
    # Only normalize Alif-based hamzas to Alif.\n    text = re.sub(r'[إأآٱ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()

q = "ابتلاء"
q_norm = normalize_arabic(q)
for prefix in ['ال', 'بال', 'وال', 'فال', 'كال', 'لل']:
    if q_norm.startswith(prefix):
        q_norm = q_norm[len(prefix):]
        break
print(f"q_norm after prefix strip: '{q_norm}'")

with Session(engine) as session:
    m1 = session.query(Morphology).filter(Morphology.text == q_norm).first()
    m2 = session.query(Morphology).filter(Morphology.lemma == q_norm).first()
    m3 = session.query(Morphology).filter(Morphology.root == q_norm).first()
    print(f"Exact text match: {m1.root if m1 else None}, lemma={m1.lemma if m1 else None}")
    print(f"Exact lemma match: {m2.root if m2 else None}, text={m2.text if m2 else None}")
    print(f"Exact root match: {m3.root if m3 else None}")
    
    morph = m1 or m2 or m3
    print(f"\nFinal root: {morph.root if morph else 'NOT FOUND'}")
    
    if morph:
        with open('enrichment_map.json') as f:
            em = json.load(f)
        print(f"Root '{morph.root}' in enrichment_map: {morph.root in em}")
        if morph.root in em:
            print(em[morph.root])
