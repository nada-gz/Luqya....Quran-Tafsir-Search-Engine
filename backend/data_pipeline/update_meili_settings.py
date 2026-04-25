import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import meilisearch

client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')
index = client.index('quran')

settings = {
    'searchableAttributes': [
        'text_uthmani',
        'text_normalized',
        'roots',
        'themes',
        'lemmas',
        'tafsir_simple_moyassar',
        'tafsir_simple_saadi',
        'tafsir_advanced_katheer',
        'tafsir_advanced_tabari'
    ],
    'filterableAttributes': ['surah_number', 'ayah_number'],
    'sortableAttributes': ['surah_number', 'ayah_number'],
    'typoTolerance': {
        'enabled': True,
        'minWordSizeForTypos': {
            'oneTypo': 5,
            'twoTypos': 9
        },
        'disableOnAttributes': ['themes', 'roots'] # Disable typos on categorical/semantic fields
    },
    'rankingRules': [
        'words',
        'typo',
        'proximity',
        'attribute',
        'sort',
        'exactness'
    ]
}

print("Updating Meilisearch settings...")
index.update_settings(settings)
print("Settings updated successfully.")
