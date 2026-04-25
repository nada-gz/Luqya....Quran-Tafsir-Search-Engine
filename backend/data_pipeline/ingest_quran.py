import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import meilisearch
import requests
import re
import json
import time
from sqlmodel import Session, select
from database import engine
from models import Surah, Ayah, Tafsir

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

def fetch_json(session, url):
    print(f"Fetching: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    response = session.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch {url}: Status {response.status_code}")
        response.raise_for_status()
    return response.json()

def ingest_all():
    session = requests.Session()
    # 1. Fetch Surah Metadata
    surah_info_url = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/info.json"
    surah_info = fetch_json(session, surah_info_url)
    
    # 2. Fetch Full Uthmani Quran
    quran_text_url = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/editions/ara-quranuthmanihaf.json"
    quran_data = fetch_json(session, quran_text_url)
    
    # 3. Setup Tafsir Slugs (spa5k/tafsir_api)
    tafsir_slugs = {
        'moyassar': 'ar-tafsir-muyassar',
        'saadi': 'ar-tafseer-al-saddi',
        'katheer': 'ar-tafsir-ibn-kathir',
        'tabari': 'ar-tafsir-al-tabari'
    }
    
    print("Preparing Meilisearch Index...")
    index = client.index('quran')
    index.delete_all_documents()
    
    from sqlalchemy import text
    with Session(engine) as db_session:
        # Clear local metadata
        print("Cleaning up database...")
        db_session.execute(text("DELETE FROM tafsir"))
        db_session.execute(text("DELETE FROM ayah"))
        db_session.execute(text("DELETE FROM surah"))
        db_session.commit()
        
        # Populate Surahs
        print("Populating Surah metadata...")
        surah_map = {}
        for s in surah_info['chapters']:
            new_surah = Surah(
                number=s['chapter'],
                name_arabic=s['arabicname'],
                name_english=s['englishname'],
                revelation_type=s['revelation']
            )
            db_session.add(new_surah)
            db_session.commit()
            surah_map[s['chapter']] = new_surah.id
            
        # Ingest Ayahs in batches
        all_ayahs = quran_data['quran']
        batch_size = 100
        total_ayahs = len(all_ayahs)
        
        print(f"Ingesting {total_ayahs} ayahs...")
        
        current_surah_num = -1
        tafsir_cache = {} 
        documents = []
        
        for i, ayah_raw in enumerate(all_ayahs):
            surah_num = ayah_raw['chapter']
            ayah_num = ayah_raw['verse']
            text_val = ayah_raw['text']
            
            # Load new Tafsirs if Surah changed
            if surah_num != current_surah_num:
                print(f"Loading Tafsirs for Surah {surah_num}...")
                time.sleep(0.1) # Be nice to GitHub Raw
                tafsir_cache = {}
                for key, slug in tafsir_slugs.items():
                    try:
                        url = f"https://raw.githubusercontent.com/spa5k/tafsir_api/main/tafsir/{slug}/{surah_num}.json"
                        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                        resp = session.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            tafsir_cache[key] = {t['ayah']: t['text'] for t in data.get('ayahs', [])}
                        else:
                            tafsir_cache[key] = {}
                    except Exception as e:
                        tafsir_cache[key] = {}
                current_surah_num = surah_num
            
            # Add ayah to SQLite
            new_ayah = Ayah(
                surah_id=surah_map[surah_num],
                ayah_number=ayah_num,
                text_uthmani=text_val
            )
            db_session.add(new_ayah)
            db_session.flush() 
            
            # Save Tafsirs to SQLite
            for key in tafsir_slugs.keys():
                content = tafsir_cache.get(key, {}).get(ayah_num, "")
                if content:
                    t_type = f"simple_{key}" if key in ['moyassar', 'saadi'] else f"advanced_{key}"
                    db_session.add(Tafsir(
                        ayah_id=new_ayah.id,
                        tafsir_type=t_type,
                        text=content
                    ))
            
            # Prepare Meilisearch Document
            doc = {
                'id': new_ayah.id,
                'surah_number': surah_num,
                'surah_name': next(s['arabicname'] for s in surah_info['chapters'] if s['chapter'] == surah_num),
                'ayah_number': ayah_num,
                'text_uthmani': text_val,
                'text_normalized': normalize_arabic(text_val),
                'tafsir_simple_moyassar': tafsir_cache.get('moyassar', {}).get(ayah_num, ""),
                'tafsir_simple_saadi': tafsir_cache.get('saadi', {}).get(ayah_num, ""),
                'tafsir_advanced_katheer': tafsir_cache.get('katheer', {}).get(ayah_num, ""),
                'tafsir_advanced_tabari': tafsir_cache.get('tabari', {}).get(ayah_num, ""),
                'roots': [], 
                'lemmas': []
            }
            documents.append(doc)
            
            if len(documents) >= batch_size:
                index.add_documents(documents)
                documents = []
                print(f"Indexed {i+1}/{total_ayahs} ayahs...")
                db_session.commit() 

        if documents:
            index.add_documents(documents)
            db_session.commit()
            
    print("Full Quran Ingestion Complete!")

if __name__ == "__main__":
    ingest_all()
