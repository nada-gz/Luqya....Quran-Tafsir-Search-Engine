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

with Session(engine) as session:
    # Check what actual text/lemma/root values look like for بلو
    rows = session.query(Morphology).filter(Morphology.root == 'بلو').limit(5).all()
    print("Rows with root='بلو' (original script):")
    for r in rows:
        print(f"  text='{r.text}' | lemma='{r.lemma}' | root='{r.root}'")
        print(f"  norm_text='{normalize_arabic(r.text)}' | norm_lemma='{normalize_arabic(r.lemma)}'")
    
    # What does the query 'ابتلاء' look like normalized?
    q = 'ابتلاء'
    print(f"\nUser query: '{q}' → normalized: '{normalize_arabic(q)}'")
