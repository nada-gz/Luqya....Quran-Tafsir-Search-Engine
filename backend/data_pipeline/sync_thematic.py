import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import sqlite3
import meilisearch
from sqlmodel import Session, select
from database import engine
from models import Surah, Ayah

client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')

def sync_thematic():
    print("Connecting to MeiliSearch...")
    index = client.index('quran')

    print("Opening topics.db...")
    topics_conn = sqlite3.connect('topics.db')
    topics_cursor = topics_conn.cursor()

    # Create a map of Ayah Reference string (e.g. "2:155") to list of topic strings
    print("Building thematic map from topics.db...")
    ayah_to_themes = {}
    
    # We fetch all topics that have ayah references
    topics_cursor.execute("SELECT name, arabic_name, ayahs FROM topics WHERE ayahs IS NOT NULL AND ayahs != ''")
    rows = topics_cursor.fetchall()
    
    for name, arabic_name, ayahs_str in rows:
        # Normalize theme name: combine English and Arabic
        theme_labels = []
        if name: theme_labels.append(name)
        if arabic_name: theme_labels.append(arabic_name)
        
        full_theme_label = " | ".join(theme_labels)
        
        # Parse ayah references (e.g. "1:1, 1:2" or "1:1,1:2")
        refs = [r.strip() for r in ayahs_str.split(',')]
        for ref in refs:
            if ref not in ayah_to_themes:
                ayah_to_themes[ref] = []
            ayah_to_themes[ref].append(full_theme_label)

    print(f"Thematic map built for {len(ayah_to_themes)} unique ayah references.")

    print("Updating Meilisearch index with thematic data...")
    with Session(engine) as session:
        # Get all ayahs from our main database
        # Use select(Ayah) for SQLModel compatibility
        statement = select(Ayah)
        results = session.exec(statement)
        
        all_ayahs = results.all()
        documents_to_update = []
        batch_size = 500
        
        for i, ayah in enumerate(all_ayahs):
            # Find surah number
            surah = session.get(Surah, ayah.surah_id)
            ref_str = f"{surah.number}:{ayah.ayah_number}"
            
            themes = ayah_to_themes.get(ref_str, [])
            
            # Prepare update document (Meilisearch works by ID)
            if themes:
                update_doc = {
                    'id': ayah.id,
                    'themes': themes
                }
                documents_to_update.append(update_doc)
            
            if len(documents_to_update) >= batch_size:
                index.update_documents(documents_to_update)
                print(f"Updated {i+1}/{len(all_ayahs)} ayahs...")
                documents_to_update = []

        if documents_to_update:
            index.update_documents(documents_to_update)
            print(f"Final batch updated. Total {len(all_ayahs)} checked.")

    # Update index settings to make 'themes' searchable
    index.update_settings({
        'searchableAttributes': [
            'text_normalized',
            'themes',
            'roots',
            'lemmas',
            'text_uthmani',
            'tafsir_simple_moyassar',
            'tafsir_simple_saadi',
            'tafsir_advanced_katheer',
            'tafsir_advanced_tabari'
        ],
        'filterableAttributes': ['surah_number', 'ayah_number', 'category']
    })
    
    topics_conn.close()
    print("Thematic synchronization complete!")

if __name__ == "__main__":
    sync_thematic()
