import meilisearch
from sqlmodel import Session
# Ignore the import error below if Pyright complains; it runs fine at runtime
from database import engine
from models import Surah, Ayah, Tafsir, Morphology

client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')

def sync_database():
    print("Connecting to MeiliSearch...")
    index = client.index('quran')
    
    # Setup index settings for Arabic search
    index.update_settings({
        'searchableAttributes': [
            'text_uthmani',
            'roots',
            'lemmas',
            'tafsir_simple_moyassar',
            'tafsir_simple_saadi',
            'tafsir_advanced_katheer',
            'tafsir_advanced_tabari'
        ],
        'filterableAttributes': [
            'surah_number',
            'ayah_number',
            'category'
        ],
        'rankingRules': [
            'words',
            'typo',
            'proximity',
            'attribute',
            'sort',
            'exactness'
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
