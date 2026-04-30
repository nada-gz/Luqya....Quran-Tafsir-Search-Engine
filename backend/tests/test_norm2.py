import re
def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u0654\u0655]', 'ا', text)
    marks = re.compile(r'[\u0610-\u061A\u064B-\u0653\u0656-\u065F\u06D6-\u06ED]')
    text = re.sub(marks, '', text)
    # Only normalize Alif-based hamzas to Alif.\n    text = re.sub(r'[إأآٱ]', 'ا', text)
    text = re.sub(r'[ى]', 'ي', text)
    text = re.sub(r'[\u0640]', '', text)
    text = re.sub(r'ا+', 'ا', text)
    return text.strip()
print(normalize_arabic("فتنة"))
print(normalize_arabic("معيشة"))
