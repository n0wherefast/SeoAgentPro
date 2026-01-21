# app/modules/competitor/competitor_analyzer.py

# from .keyword_extractor import extract_keywords_advanced
# from .text_similarity import similarity_ratio, jaccard_tokens
# from typing import Dict, Any, List
# import math

# def _text_preview(paragraphs, chars=300):
#     if not paragraphs:
#         return ""
#     joined = " ".join(paragraphs) if isinstance(paragraphs, list) else str(paragraphs)
#     return joined[:chars] + ("..." if len(joined) > chars else "")

# def _count_external_links(links: List[Dict]) -> int:
#     if not isinstance(links, list):
#         return 0
#     return sum(1 for l in links if isinstance(l, dict) and not l.get("internal"))

# def _estimate_authority(scraped: Dict) -> float:
#     """
#     Stima 'authority' su scala 0-100 usando features disponibili:
#       - num parole
#       - num headings
#       - num external links
#       - structured data presence
#       - social links presence
#       - backlinks_count (if provided by scraper)
#     """
#     text = " ".join(scraped.get("paragraphs", []) or [])
#     words = len(text.split())
#     headings = sum(len(v) for v in (scraped.get("headings") or {}).values()) if scraped.get("headings") else 0
#     external_links = _count_external_links(scraped.get("links", []))
#     structured = 1 if scraped.get("structured_data_present") else 0
#     social = len(scraped.get("social_links", []) or [])
#     backlinks = scraped.get("backlinks_count") or 0  # optional if your scraper can detect

#     # normalizzazione e pesi
#     w_words = min(1.0, words / 2000)           # 0..1
#     w_head = min(1.0, headings / 10)           # 0..1
#     w_links = min(1.0, external_links / 50)    # 0..1
#     w_struct = structured                      # 0/1
#     w_social = min(1.0, social / 20)
#     w_back = min(1.0, math.log(1 + backlinks) / 5)  # scala log per grandi valori

#     # pesi (tweakabili)
#     score = (
#         w_back * 30 +
#         w_words * 20 +
#         w_links * 15 +
#         w_head * 15 +
#         w_struct * 10 +
#         w_social * 10
#     )
#     return round(min(100, score), 2)

# def _estimate_performance(scraped: Dict) -> float:
#     """
#     Stima performance (0-100) se non è disponibile lighthouse.
#     Basato su: page_size_kb, num_requests, perf proxy se presente.
#     """
#     if scraped.get("performance_score") is not None:
#         return float(scraped.get("performance_score"))

#     size_kb = scraped.get("page_size_kb", None)
#     num_req = scraped.get("num_requests", None)

#     # se non ci sono dati, ritorna 100 (assume ok) — ma segnala che è mock
#     if size_kb is None and num_req is None:
#         return 100.0

#     score = 100.0
#     if size_kb:
#         # penalizza oltre 300KB
#         score -= max(0, (size_kb - 300) / 5)
#     if num_req:
#         score -= max(0, (num_req - 50) * 0.5)

#     return round(max(0.0, min(100.0, score)), 2)

# def analyze_competitors(your_scraped: Dict, comp_scraped: Dict) -> Dict[str, Any]:
#     # Titles & H1
#     your_title = (your_scraped.get("title") or "").strip()
#     comp_title = (comp_scraped.get("title") or "").strip()
#     your_h1s = (your_scraped.get("headings") or {}).get("h1", [])
#     comp_h1s = (comp_scraped.get("headings") or {}).get("h1", [])

#     your_h1 = your_h1s[0] if isinstance(your_h1s, list) and len(your_h1s) > 0 else ""
#     comp_h1 = comp_h1s[0] if isinstance(comp_h1s, list) and len(comp_h1s) > 0 else ""

#     title_sim = similarity_ratio(your_title, comp_title)
#     h1_sim = similarity_ratio(your_h1, comp_h1)
#     jaccard_title = jaccard_tokens(your_title, comp_title)
#     jaccard_h1 = jaccard_tokens(your_h1, comp_h1)

#     # Extract text
#     your_text = " ".join(your_scraped.get("paragraphs", []) or [])
#     comp_text = " ".join(comp_scraped.get("paragraphs", []) or [])

#     # Keyword extraction
#     your_keywords = extract_keywords_advanced(your_text, top_k=25)
#     comp_keywords = extract_keywords_advanced(comp_text, top_k=25)

#     # Keyword sets for gap analysis (use only kw strings)
#     your_kw_set = set([k["kw"] for k in your_keywords])
#     comp_kw_set = set([k["kw"] for k in comp_keywords])
#     keyword_gap = list(comp_kw_set - your_kw_set)

#     # Authority + performance
#     your_authority = _estimate_authority(your_scraped)
#     comp_authority = _estimate_authority(comp_scraped)
#     your_performance = _estimate_performance(your_scraped)
#     comp_performance = _estimate_performance(comp_scraped)

#     # content structure metrics
#     def content_metrics(scr):
#         paragraphs = scr.get("paragraphs") or []
#         words = len((" ".join(paragraphs)).split())
#         headings = scr.get("headings") or {}
#         depth = sum(1 for h in headings.get("h2", []) + headings.get("h3", [])) if isinstance(headings, dict) else 0
#         images = len(scr.get("images", []) or [])
#         return {"words": words, "headings": sum(len(v) for v in headings.values()) if isinstance(headings, dict) else 0, "images": images, "depth": depth}

#     your_metrics = content_metrics(your_scraped)
#     comp_metrics = content_metrics(comp_scraped)

#     # overall competitiveness scoring (simple aggregate)
#     seo_gap = round(comp_authority - your_authority, 2)
#     content_quality = round(h1_sim + title_sim + (comp_metrics["words"] - your_metrics["words"]) / max(1, comp_metrics["words"] + your_metrics["words"]) , 3)
#     keyword_advantage = len(keyword_gap)

#     def build_radar_chart(your_score, competitor_score):
#         return {
#             "labels": ["authority", "content", "performance", "technical", "keywords"],
#             "datasets": [
#                 {
#                     "label": "You",
#                     "data": [
#                         your_score["authority"],
#                         your_score["content"],
#                         your_score["performance"],
#                         your_score["technical"],
#                         your_score["keyword_coverage"],
#                     ],
#                 },
#                 {
#                     "label": "Competitor",
#                     "data": [
#                         competitor_score["authority"],
#                         competitor_score["content"],
#                         competitor_score["performance"],
#                         competitor_score["technical"],
#                         competitor_score["keyword_coverage"],
#                     ],
#                 },
#             ],
#         }


#     result = {
#         "diagnostics": {
#             "your": {
#                 "title": your_title,
#                 "h1": your_h1,
#                 "text_preview": _text_preview(your_scraped.get("paragraphs", [])),
#                 "words": your_metrics["words"],
#                 "headings_count": your_metrics["headings"],
#             },
#             "competitor": {
#                 "title": comp_title,
#                 "h1": comp_h1,
#                 "text_preview": _text_preview(comp_scraped.get("paragraphs", [])),
#                 "words": comp_metrics["words"],
#                 "headings_count": comp_metrics["headings"],
#             }
#         },
#         "title_similarity": title_sim,
#         "h1_similarity": h1_sim,
#         "jaccard_title": jaccard_title,
#         "jaccard_h1": jaccard_h1,
#         "your_keywords": your_keywords,
#         "competitor_keywords": comp_keywords,
#         "keyword_gap": keyword_gap,
#         "your_authority_est": your_authority,
#         "competitor_authority_est": comp_authority,
#         "your_performance": your_performance,
#         "competitor_performance": comp_performance,
#         "your_content_metrics": your_metrics,
#         "competitor_content_metrics": comp_metrics,
#         "overall_competitiveness": {
#             "seo_gap": seo_gap,
#             "content_quality": content_quality,
#             "keyword_advantage": keyword_advantage
#         },
#         "radar": build_radar_chart(your_scores, competitor_scores)

#     }

#     return result

from .keyword_extractor import extract_keywords_advanced
from .text_similarity import similarity_ratio, jaccard_tokens
from typing import Dict, Any, List
import math


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------
def _text_preview(paragraphs, chars=300):
    if not paragraphs:
        return ""
    joined = " ".join(paragraphs) if isinstance(paragraphs, list) else str(paragraphs)
    return joined[:chars] + ("..." if len(joined) > chars else "")


def _count_external_links(links: List[Dict]) -> int:
    if not isinstance(links, list):
        return 0
    return sum(1 for l in links if isinstance(l, dict) and not l.get("internal"))


# ---------------------------------------------------------
# Authority Estimation
# ---------------------------------------------------------
def _estimate_authority(scraped: Dict) -> float:
    text = " ".join(scraped.get("paragraphs", []) or [])
    words = len(text.split())

    headings = sum(len(v) for v in (scraped.get("headings") or {}).values()) if scraped.get("headings") else 0
    external_links = _count_external_links(scraped.get("links", []))

    structured = 1 if scraped.get("structured_data_present") else 0
    social = len(scraped.get("social_links", []) or [])
    backlinks = scraped.get("backlinks_count") or 0

    # Normalized weights
    w_words = min(1.0, words / 2000)
    w_head = min(1.0, headings / 10)
    w_links = min(1.0, external_links / 50)
    w_struct = structured
    w_social = min(1.0, social / 20)
    w_back = min(1.0, math.log(1 + backlinks) / 5)

    score = (
        w_back * 30 +
        w_words * 20 +
        w_links * 15 +
        w_head * 15 +
        w_struct * 10 +
        w_social * 10
    )

    return round(min(100, score), 2)


# ---------------------------------------------------------
# Performance Estimation (fallback if no Lighthouse)
# ---------------------------------------------------------
def _estimate_performance(scraped: Dict) -> float:
    if scraped.get("performance_score") is not None:
        return float(scraped.get("performance_score"))

    size_kb = scraped.get("page_size_kb", None)
    num_req = scraped.get("num_requests", None)

    if size_kb is None and num_req is None:
        return 100.0

    score = 100.0

    if size_kb:
        score -= max(0, (size_kb - 300) / 5)

    if num_req:
        score -= max(0, (num_req - 50) * 0.5)

    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------
# Radar Chart Builder
# ---------------------------------------------------------
def build_radar_chart(your_score, competitor_score):
    return {
        "labels": ["authority", "content", "performance", "technical", "keyword_coverage"],
        "datasets": [
            {
                "label": "You",
                "data": [
                    your_score["authority"],
                    your_score["content"],
                    your_score["performance"],
                    your_score["technical"],
                    your_score["keyword_coverage"],
                ],
            },
            {
                "label": "Competitor",
                "data": [
                    competitor_score["authority"],
                    competitor_score["content"],
                    competitor_score["performance"],
                    competitor_score["technical"],
                    competitor_score["keyword_coverage"],
                ],
            },
        ],
    }


# ---------------------------------------------------------
# MAIN COMPETITOR ANALYZER
# ---------------------------------------------------------
def analyze_competitors(your_scraped: Dict, comp_scraped: Dict) -> Dict[str, Any]:

    # Titles & H1
    your_title = (your_scraped.get("title") or "").strip()
    comp_title = (comp_scraped.get("title") or "").strip()

    your_h1s = (your_scraped.get("headings") or {}).get("h1", [])
    comp_h1s = (comp_scraped.get("headings") or {}).get("h1", [])

    your_h1 = your_h1s[0] if your_h1s else ""
    comp_h1 = comp_h1s[0] if comp_h1s else ""

    title_sim = similarity_ratio(your_title, comp_title)
    h1_sim = similarity_ratio(your_h1, comp_h1)
    jaccard_title = jaccard_tokens(your_title, comp_title)
    jaccard_h1 = jaccard_tokens(your_h1, comp_h1)

    # Extract text
    your_text = " ".join(your_scraped.get("paragraphs", []) or [])
    comp_text = " ".join(comp_scraped.get("paragraphs", []) or [])

    # Extract keywords
    your_keywords = extract_keywords_advanced(your_text, top_k=25)
    comp_keywords = extract_keywords_advanced(comp_text, top_k=25)

    your_kw_set = {k["kw"] for k in your_keywords}
    comp_kw_set = {k["kw"] for k in comp_keywords}

    keyword_gap = list(comp_kw_set - your_kw_set)

    # Authority + performance
    your_authority = _estimate_authority(your_scraped)
    comp_authority = _estimate_authority(comp_scraped)

    your_performance = _estimate_performance(your_scraped)
    comp_performance = _estimate_performance(comp_scraped)

    # ---------------------------------------------------------
    # Content Metrics
    # ---------------------------------------------------------
    def content_metrics(scr):
        paragraphs = scr.get("paragraphs") or []
        words = len((" ".join(paragraphs)).split())

        headings = scr.get("headings") or {}
        images = len(scr.get("images", []) or [])

        depth = sum(
            1 for h in headings.get("h2", []) + headings.get("h3", [])
        ) if isinstance(headings, dict) else 0

        return {
            "words": words,
            "headings": sum(len(v) for v in headings.values()) if isinstance(headings, dict) else 0,
            "images": images,
            "depth": depth
        }

    your_metrics = content_metrics(your_scraped)
    comp_metrics = content_metrics(comp_scraped)

    # ---------------------------------------------------------
    # Build scores for radar
    # ---------------------------------------------------------

    # content score normalized to 0–100
    content_score_you = min(100, (your_metrics["words"] / max(1, comp_metrics["words"])) * 100)
    content_score_comp = 100  # competitor baseline

    # keyword coverage
    keyword_coverage_you = max(0, 100 - len(keyword_gap) * 5)
    keyword_coverage_comp = 100

    # technical placeholder (will be replaced later by real technical score)
    technical_you = 50
    technical_comp = 50

    your_scores = {
        "authority": your_authority,
        "content": content_score_you,
        "performance": your_performance,
        "technical": technical_you,
        "keyword_coverage": keyword_coverage_you,
    }

    competitor_scores = {
        "authority": comp_authority,
        "content": content_score_comp,
        "performance": comp_performance,
        "technical": technical_comp,
        "keyword_coverage": keyword_coverage_comp,
    }

    # ---------------------------------------------------------
    # RESULT STRUCTURE
    # ---------------------------------------------------------
    result = {
        "diagnostics": {
            "your": {
                "title": your_title,
                "h1": your_h1,
                "text_preview": _text_preview(your_scraped.get("paragraphs", [])),
                "words": your_metrics["words"],
                "headings_count": your_metrics["headings"],
            },
            "competitor": {
                "title": comp_title,
                "h1": comp_h1,
                "text_preview": _text_preview(comp_scraped.get("paragraphs", [])),
                "words": comp_metrics["words"],
                "headings_count": comp_metrics["headings"],
            },
        },
        "title_similarity": title_sim,
        "h1_similarity": h1_sim,
        "jaccard_title": jaccard_title,
        "jaccard_h1": jaccard_h1,
        "your_keywords": your_keywords,
        "competitor_keywords": comp_keywords,
        "keyword_gap": keyword_gap,
        "your_authority_est": your_authority,
        "competitor_authority_est": comp_authority,
        "your_performance": your_performance,
        "competitor_performance": comp_performance,
        "your_content_metrics": your_metrics,
        "competitor_content_metrics": comp_metrics,
        "overall_competitiveness": {
            "seo_gap": round(comp_authority - your_authority, 2),
            "content_quality": round(
                h1_sim +
                title_sim +
                (comp_metrics["words"] - your_metrics["words"]) /
                max(1, comp_metrics["words"] + your_metrics["words"]),
                3
            ),
            "keyword_advantage": len(keyword_gap),
        },

        # ⭐ RADAR FINALMENTE FUNZIONANTE ⭐
        "radar": build_radar_chart(your_scores, competitor_scores)
    }

    return result
