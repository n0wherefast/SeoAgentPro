# app/modules/competitor/ranking.py
from typing import Dict

def compute_simple_scores(scan: Dict) -> Dict:
    """
    Estrae metriche sintetiche da uno scan:
      - authority_est (0-100)
      - content_score (0-100)
      - performance (0-100)
      - technical_score (0-100)
      - keyword_coverage (0-100)
    scan: output di scrape_url (deve contenere keys usate dal detector)
    """
    # Authority: basato su link count se presente
    links = scan.get("links", [])
    authority = min(100, len(links) * 1.2) if links else None

    # Content: wordcount e headings
    paragraphs = scan.get("paragraphs", []) or []
    wordcount = sum(len(p.split()) for p in paragraphs)
    content_score = min(100, int(wordcount / 10)) if wordcount > 0 else None

    # Performance: preferiamo usare performance_score se presente (da PSI)
    perf = scan.get("performance_score")
    performance_score = perf if isinstance(perf, (int, float)) else None

    # Technical: presenza canonical, robots, sitemap, https, schema
    tech = 0
    tech += 25 if scan.get("canonical") else 0
    tech += 25 if scan.get("robots_txt_found") else 0
    tech += 25 if scan.get("sitemap_found") else 0
    tech += 25 if scan.get("https") else 0
    technical_score = tech if tech > 0 else None

    # Keyword coverage: top tokens presence in title/h1
    text = " ".join(paragraphs)
    tokens = scan.get("top_tokens", [])  # se lo scraper le fornisce
    kw_cov = 0
    if tokens:
        title = (scan.get("title") or "").lower()
        h1s = " ".join(scan.get("headings", {}).get("h1", [])).lower()
        hits = sum(1 for t in tokens if t in title or t in h1s)
        kw_cov = int(100 * hits / max(1, len(tokens)))
    else:
        kw_cov = 40  # default neutral

    return {
        "authority": int(authority) if authority is not None else None,
        "content": int(min(100, content_score)) if content_score is not None else None,
        "performance": int(min(100, performance_score)) if performance_score is not None else None,
        "technical": int(min(100, technical_score)) if technical_score is not None else None,
        "keyword_coverage": int(kw_cov)
    }


def rank_competitor(yours: Dict, comp: Dict) -> Dict:
    """
    Confronta due chip di metriche e produce:
      - winner: 'you' / 'competitor' / 'tie'
      - scores: both metrics
      - delta per dimension
    """
    my_scores = compute_simple_scores(yours)
    comp_scores = compute_simple_scores(comp)

    # overall: media pesata (weights can be tuned)
    weights = {
        "authority": 0.30,
        "content": 0.25,
        "performance": 0.20,
        "technical": 0.15,
        "keyword_coverage": 0.10
    }
    def weighted(scores):
        total = 0
        weight_sum = 0
        for k in weights:
            value = scores.get(k)
            if value is not None:
                total += value * weights[k]
                weight_sum += weights[k]
        # Normalizza in base ai pesi che hanno valori non-None
        return total / weight_sum if weight_sum > 0 else 0

    my_overall = weighted(my_scores)
    comp_overall = weighted(comp_scores)

    if my_overall > comp_overall + 2:
        winner = "you"
    elif comp_overall > my_overall + 2:
        winner = "competitor"
    else:
        winner = "tie"

    # delta: gestisce None values
    delta = {}
    for k in my_scores.keys():
        my_val = my_scores.get(k)
        comp_val = comp_scores.get(k)
        if my_val is not None and comp_val is not None:
            delta[k] = comp_val - my_val
        elif comp_val is not None:
            delta[k] = comp_val
        elif my_val is not None:
            delta[k] = -my_val
        else:
            delta[k] = None

    return {
        "winner": winner,
        "my_overall": round(my_overall, 2) if my_overall else 0,
        "comp_overall": round(comp_overall, 2) if comp_overall else 0,
        "my_scores": my_scores,
        "comp_scores": comp_scores,
        "delta": delta
    }
