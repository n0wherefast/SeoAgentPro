# app/modules/competitor/text_similarity.py
from difflib import SequenceMatcher

def similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a.lower(), b.lower()).ratio(), 3)

def jaccard_tokens(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    import re
    ta = set(re.findall(r"[a-zA-Zà-ú]{3,}", a.lower()))
    tb = set(re.findall(r"[a-zA-Zà-ú]{3,}", b.lower()))
    if not ta or not tb:
        return 0.0
    inter = ta.intersection(tb)
    union = ta.union(tb)
    return round(len(inter) / len(union), 3)

