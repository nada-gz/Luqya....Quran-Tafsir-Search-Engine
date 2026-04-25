import sys, os; sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import meilisearch

client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')
index = client.index('quran')

settings = {
    'typoTolerance': {
        'enabled': False
    },
    'rankingRules': [
        'surah_number:asc',
        'ayah_number:asc',
        'exactness',
        'words',
        'proximity',
        'attribute'
    ]
}

print("Updating Meilisearch settings...")
task = index.update_settings(settings)
print(f"Update triggered. Task UID: {task.task_uid}")
