import meilisearch
import sys
client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')
index = client.index('quran')

res = index.search('الفتنة', {
    'attributesToSearchOn': ['themes', 'text_normalized'],
    'limit': 5
})
print("Search 'الفتنة' hits:", len(res['hits']))

res2 = index.search('Trial', {
    'attributesToSearchOn': ['themes'],
    'limit': 5
})
print("Search 'Trial' hits:", len(res2['hits']))
