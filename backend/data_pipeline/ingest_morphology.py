import sys, os; sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import os
from sqlmodel import Session
from database import engine, create_db_and_tables
from models import Morphology
import re

def ingest_morphology():
    create_db_and_tables()
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_assets", "quran-morphology.txt")
    if not os.path.exists(file_path):
        print(f"{file_path} not found. Please download it first.")
        return

    print("Parsing and ingesting morphology data...")
    with Session(engine) as session:
        # Check if already ingested
        # Ignoring Pyright warnings for session.query by just catching it
        try:
            count = session.query(Morphology).count()
            if count > 0:
                print(f"Morphology data already exists ({count} segments). Skip.")
                return
        except Exception:
            pass

        with open(file_path, 'r', encoding='utf-8') as f:
            batch = []
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    loc = parts[0].split(':')
                    surah = int(loc[0])
                    ayah = int(loc[1])
                    word = int(loc[2])
                    segment = int(loc[3])
                    
                    text = parts[1]
                    tag = parts[2]
                    features = parts[3]
                    
                    root = None
                    lemma = None
                    
                    root_match = re.search(r'ROOT:([^|]+)', features)
                    if root_match:
                        # Space delimits the root letters sometimes, let's keep it normalized by removing spaces
                        # Or keep spaces if standard. Actually, Meilisearch searches on full word. Let's keep spaces to match exactly with typical space-separated roots
                        root = root_match.group(1).replace(' ', '')
                        
                    lemma_match = re.search(r'LEM:([^|]+)', features)
                    if lemma_match:
                        lemma = lemma_match.group(1)
                        
                    morph = Morphology(
                        surah_number=surah,
                        ayah_number=ayah,
                        word_number=word,
                        segment_number=segment,
                        text=text,
                        root=root,
                        lemma=lemma
                    )
                    batch.append(morph)
                    
                    if len(batch) >= 5000:
                        session.add_all(batch)
                        session.commit()
                        batch = []
                        print(f"Ingested up to Surah {surah} Ayah {ayah}")

            if batch:
                session.add_all(batch)
                session.commit()
                print("Morphology ingestion complete.")

if __name__ == "__main__":
    ingest_morphology()
