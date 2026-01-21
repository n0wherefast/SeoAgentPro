# app/modules/competitor/keyword_extractor.py
import re
from collections import Counter
from typing import List, Tuple

# stopwords minimale (it + en) — estendi se vuoi
STOPWORDS = set("""
the a and of to in for with that this from your are not you but have was were has had will can per con da di il la le i un una
""".split())

def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    toks = re.findall(r"[a-zA-Zà-úÀ-Ú]{3,}", text.lower())
    return [t for t in toks if t not in STOPWORDS]

def top_ngrams(text: str, n=1, top_k=20) -> List[Tuple[str,int]]:
    toks = _tokenize(text)
    if n == 1:
        ctr = Counter(toks)
        return ctr.most_common(top_k)
    ngrams = zip(*(toks[i:] for i in range(n)))
    ngrams = [" ".join(ng) for ng in ngrams]
    ctr = Counter(ngrams)
    return ctr.most_common(top_k)

def extract_keywords_advanced(text: str, top_k=20):
    """
    Combina unigram + bigram + trigram, ritorna keywords ordinale.
    Restituisce dizionario con ranking e score grezzo.
    """
    if not text or len(text.strip()) == 0:
        return []

    unigrams = top_ngrams(text, n=1, top_k=top_k*2)
    bigrams = top_ngrams(text, n=2, top_k=top_k)
    trigrams = top_ngrams(text, n=3, top_k=top_k)

    # Score mix: unigram score base, bigram *1.3, trigram *1.6
    scores = Counter()
    for term, cnt in unigrams:
        scores[term] += cnt * 1.0
    for term, cnt in bigrams:
        scores[term] += cnt * 1.3
    for term, cnt in trigrams:
        scores[term] += cnt * 1.6

    # keep top_k
    top = scores.most_common(top_k)
    return [{"kw": k, "score": float(v)} for k, v in top]
# alias per compatibilità con il router
def extract_keywords(text: str, top_k=20):
    return extract_keywords_advanced(text, top_k=top_k)
