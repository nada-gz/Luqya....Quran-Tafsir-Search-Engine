from main import search
try:
    print(search(q="ابتلاء", mode="semantic_root"))
except Exception as e:
    import traceback
    traceback.print_exc()
