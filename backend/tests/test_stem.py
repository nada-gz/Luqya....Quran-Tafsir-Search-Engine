from database import engine
from sqlmodel import Session
from models import Morphology
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

q = 'ابتلاء'
q_norm = normalize_arabic(q)
print(f"q_norm = '{q_norm}'")
stem = q_norm[:3]
print(f"stem = '{stem}'")

with Session(engine) as session:
    candidates = session.query(Morphology).filter(
        Morphology.text.like(f"%{stem}%") |
        Morphology.lemma.like(f"%{stem}%")
    ).limit(200).all()
    print(f"Candidates fetched: {len(candidates)}")
    for row in candidates[:10]:
        nt = normalize_arabic(row.text)
        nl = normalize_arabic(row.lemma)
        match = (nt == q_norm or nl == q_norm)
        print(f"  text='{row.text}' norm='{nt}' lemma='{row.lemma}' norm_l='{nl}' root='{row.root}' MATCH={match}")
