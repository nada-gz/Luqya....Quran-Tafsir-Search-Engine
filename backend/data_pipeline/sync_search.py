import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import meilisearch
from sqlmodel import Session
import re
# Ignore the import error below if Pyright complains; it runs fine at runtime
from database import engine
from models import Surah, Ayah, Tafsir, Morphology

client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')

def normalize_arabic(text):
    if not text:
        return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    marks = re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]')
    text = re.sub(marks, '', text)
    text = re.sub(r'[إأآٱءئؤ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    
    # Map dagger alif (\u0670) to normal alif
    text = re.sub(r'\u0670', 'ا', text)
    
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

    text = re.sub(r'ا+', 'ا', text)
    return text.strip()

def sync_database():
    print("Connecting to MeiliSearch...")
    index = client.index('quran')
    
    # Setup index settings for strict Arabic search
    index.update_settings({
        'searchableAttributes': [
            'text_normalized',
            'roots',
            'lemmas',
            'text_uthmani',
            'tafsir_simple_moyassar',
            'tafsir_simple_saadi',
            'tafsir_advanced_katheer',
            'tafsir_advanced_tabari'
        ],
        'typoTolerance': {
            'enabled': False
        },
        'rankingRules': [
            'exactness',
            'words',
            'surah_number:asc',
            'ayah_number:asc',
            'proximity',
            'attribute'
        ],
        'filterableAttributes': [
            'surah_number',
            'ayah_number',
            'category'
        ]
    })
    
    print("Reading data from SQLite...")
    with Session(engine) as session:
        # Use session.query to be compatible with SQLModel's underlying SQLAlchemy session
        ayahs = session.query(Ayah).all()
        documents = []
        for ayah in ayahs:
            surah = session.query(Surah).filter(Surah.id == ayah.surah_id).first()
            tafsirs = session.query(Tafsir).filter(Tafsir.ayah_id == ayah.id).all()
            morphs = session.query(Morphology).filter(Morphology.surah_number == surah.number, Morphology.ayah_number == ayah.ayah_number).all()
            
            roots = list(set([m.root for m in morphs if m.root]))
            lemmas = list(set([m.lemma for m in morphs if m.lemma]))
            
            doc = {
                'id': ayah.id,
                'surah_number': surah.number,
                'surah_name': surah.name_arabic,
                'ayah_number': ayah.ayah_number,
                'text_uthmani': ayah.text_uthmani,
                'text_normalized': normalize_arabic(ayah.text_uthmani),
                'category': ayah.category or '',
                'roots': roots,
                'lemmas': lemmas,
                'tafsir_simple_moyassar': '',
                'tafsir_simple_saadi': '',
                'tafsir_advanced_katheer': '',
                'tafsir_advanced_tabari': ''
            }
            
            for t in tafsirs:
                doc[f'tafsir_{t.tafsir_type}'] = t.text
                
            documents.append(doc)
            
        if documents:
            print(f"Indexing {len(documents)} ayahs into MeiliSearch...")
            task = index.add_documents(documents)
            print(f"Done. Task UID: {task.task_uid}")
            
if __name__ == "__main__":
    sync_database()
