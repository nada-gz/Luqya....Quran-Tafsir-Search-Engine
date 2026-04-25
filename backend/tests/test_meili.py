import meilisearch
client = meilisearch.Client('http://127.0.0.1:7700', 'quran_search_master_key')
index = client.index('quran')
res = index.search('ابتلاء فتنة بلاء صبر اختبار بلو', {
    'attributesToSearchOn': ['roots', 'themes', 'lemmas', 'text_normalized'],
    'matchingStrategy': 'any',
    'limit': 5
})
print(len(res['hits']))
