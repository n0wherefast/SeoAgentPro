"""
Competitor Intelligence Module
Provides keyword extraction, clustering, ranking, and competitive analysis utilities.
"""

from .keyword_extractor import extract_keywords_advanced, extract_keywords
from .keyword_clustering import cluster_keywords
from .ranking import compute_simple_scores, rank_competitor
from .text_similarity import similarity_ratio, jaccard_tokens
from .lighthouse_client import run_performance_engine, fetch_pagespeed_score
from .radar import radar_payload

__all__ = [
    # Keyword tools
    "extract_keywords_advanced",
    "extract_keywords",
    "cluster_keywords",
    
    # Ranking & comparison
    "compute_simple_scores",
    "rank_competitor",
    "similarity_ratio",
    "jaccard_tokens",
    
    # Performance
    "run_performance_engine",
    "fetch_pagespeed_score",
    
    # Visualization
    "radar_payload"
]
