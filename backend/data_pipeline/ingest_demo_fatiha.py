import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import requests
from sqlmodel import Session
from database import engine, create_db_and_tables
from models import Surah, Ayah, Tafsir
import time

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure requests session with retries
session_req = requests.Session()
session_req.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
retry = Retry(connect=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session_req.mount('http://', adapter)
session_req.mount('https://', adapter)

TAFSIR_SOURCES = {
    'simple_moyassar': 'ar-tafsir-muyassar',
    'simple_saadi': 'ar-tafseer-al-saddi',
    'advanced_katheer': 'ar-tafsir-ibn-kathir',
    'advanced_tabari': 'ar-tafsir-al-tabari'
}

def fetch_surahs(session: Session):
    print("Fetching Surahs...")
    response = session_req.get("https://api.quran.com/api/v4/chapters", timeout=10)
    if response.status_code != 200:
        print("Failed to fetch Surahs")
        return
        
    data = response.json()
    for chapter in data.get("chapters", []):
        surah = Surah(
            number=chapter["id"],
            name_arabic=chapter["name_arabic"],
            name_english=chapter["name_simple"],
            revelation_type=chapter["revelation_place"]
        )
        existing = session.query(Surah).filter(Surah.number == surah.number).first()
        if not existing:
            session.add(surah)
    session.commit()
    print("Surahs fetched and saved.")

def fetch_ayahs_for_surah(session: Session, surah_number: int):
    print(f"Fetching Ayahs for Surah {surah_number}...")
    response = session_req.get(f"https://api.quran.com/api/v4/quran/verses/uthmani?chapter_number={surah_number}", timeout=10)
    if response.status_code != 200:
        print(f"Failed to fetch Ayahs for Surah {surah_number}")
        return
        
    data = response.json()
    surah = session.query(Surah).filter(Surah.number == surah_number).first()
    if not surah:
        print(f"Surah {surah_number} not found in DB.")
        return

    verses = data.get("verses", [])
    for verse in verses:
        verse_key = verse["verse_key"] # e.g., "1:1"
        ayah_number = int(verse_key.split(":")[1])
        text_uthmani = verse["text_uthmani"]
        
        existing = session.query(Ayah).filter(Ayah.surah_id == surah.id, Ayah.ayah_number == ayah_number).first()
        if not existing:
            ayah = Ayah(
                surah_id=surah.id,
                ayah_number=ayah_number,
                text_uthmani=text_uthmani
            )
            session.add(ayah)
    session.commit()
    print(f"Ayahs for Surah {surah_number} fetched and saved.")

def fetch_tafsirs_for_surah(session: Session, surah_number: int):
    print(f"Fetching Tafsirs for Surah {surah_number}... This may take a moment.")
    
    surah = session.query(Surah).filter(Surah.number == surah_number).first()
    if not surah:
        return
        
    ayahs = session.query(Ayah).filter(Ayah.surah_id == surah.id).all()
    
    for ayah in ayahs:
        for t_type, t_id in TAFSIR_SOURCES.items():
            existing = session.query(Tafsir).filter(Tafsir.ayah_id == ayah.id, Tafsir.tafsir_type == t_type).first()
            if existing:
                continue
                
            url = f"https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir/{t_id}/{surah_number}/{ayah.ayah_number}.json"
            
            try:
                response = session_req.get(url, timeout=10)
                if response.status_code == 200:
                    t_data = response.json()
                    tafsir = Tafsir(
                        ayah_id=ayah.id,
                        tafsir_type=t_type,
                        text=t_data.get("text", "")
                    )
                    session.add(tafsir)
                else:
                    print(f"  - Failed {t_type} for Ayah {ayah.ayah_number} - Status: {response.status_code}")
            except Exception as e:
                print(f"  - Error fetching {t_type} for Ayah {ayah.ayah_number}: {e}")
            
            # small delay to prevent overwhelming the API
            time.sleep(0.1)
                
        session.commit()
    print(f"Completed Tafsirs for Surah {surah_number}")

def main():
    print("Initializing Database...")
    create_db_and_tables()
    
    with Session(engine) as session:
        fetch_surahs(session)
        # We start by testing with Surah Al-Fatiha (Surah 1)
        test_surah = 1
        fetch_ayahs_for_surah(session, test_surah)
        fetch_tafsirs_for_surah(session, test_surah)
        print("Initial verification ingestion complete! Surah 1 is fully loaded.")

if __name__ == "__main__":
    main()
