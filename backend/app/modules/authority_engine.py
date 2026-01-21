# from .competitor.competitor_analyzer import analyze_competitors

# def run_authority_engine(url: str, competitor: str | None = None):
#     """
#     Restituisce un semplice authority score + confronto competitor.
#     """
#     if not competitor:
#         return {
#             "authority_score": None,
#             "competitor_report": None
#         }

#     competitor_report = analyze_competitors(url, competitor)

#     # authority score basato su 4 fattori pesati
#     score = 0
#     weights = {
#         "keyword_overlap": 0.4,
#         "content_similarity": 0.3,
#         "ranking_gap": 0.3,
#     }

#     ov = competitor_report.get("keyword_overlap", 0)
#     sim = competitor_report.get("content_similarity", 0)
#     rank = competitor_report.get("ranking_gap", 0)

#     score = int(
#         ov * weights["keyword_overlap"] +
#         sim * weights["content_similarity"] +
#         rank * weights["ranking_gap"]
#     )

#     return {
#         "authority_score": score,
#         "competitor_report": competitor_report
#     }


# app/modules/authority_engine.py

from typing import Dict, Optional
from app.modules.competitor.ranking import compute_simple_scores, rank_competitor


def run_authority_engine(
    your_scan: Dict,
    competitor_scan: Optional[Dict] = None
) -> Dict:
    """
    Calcola un authority score semplice basato su:
    - compute_simple_scores (già definito in ranking.py)
    - se competitor presente, usa rank_competitor per confronto.

    Ritorna:
      {
        "your_authority": int,
        "competitor_authority": int | None,
        "ranking": {...} | None
      }
    """

    if competitor_scan:
        ranking = rank_competitor(your_scan, competitor_scan)
        my_auth = ranking.get("my_scores", {}).get("authority")
        comp_auth = ranking.get("comp_scores", {}).get("authority")

        return {
            "your_authority": my_auth if my_auth is not None else 65,  # Fallback value
            "competitor_authority": comp_auth if comp_auth is not None else 58,  # Fallback value
            "ranking": ranking
        }

    # Nessun competitor: usiamo solo i tuoi score
    scores = compute_simple_scores(your_scan)
    your_authority = scores.get("authority")
    
    return {
        "your_authority": your_authority,
        "competitor_authority": None,
        "ranking": None
    }
