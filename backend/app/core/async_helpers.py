"""
Async helpers for parallelizing SEO analysis tasks.
Enables concurrent execution of CPU-heavy operations like keyword extraction.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=4)


async def async_extract_keywords(text: str, top_k: int = 50):
    """
    Async wrapper for keyword extraction.
    Runs in thread pool to avoid blocking event loop.
    """
    try:
        from app.modules.competitor.keyword_extractor import extract_keywords_advanced
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            extract_keywords_advanced,
            text,
            top_k
        )
        return result
    except Exception as e:
        logger.error(f"❌ async_extract_keywords failed: {e}")
        return []


async def async_cluster_keywords(keywords: list, n_clusters: int = 6):
    """
    Async wrapper for keyword clustering.
    Runs in thread pool to avoid blocking event loop.
    """
    try:
        from app.modules.competitor.keyword_clustering import cluster_keywords
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            cluster_keywords,
            keywords,
            n_clusters
        )
        return result
    except Exception as e:
        logger.error(f"❌ async_cluster_keywords failed: {e}")
        return {"clusters": {}, "centroids": []}


async def parallel_keyword_analysis(my_text: str, comp_text: str, top_k: int = 50):
    """
    Extract keywords from both texts in parallel.
    
    Returns:
        (my_keywords, comp_keywords) tuple
    """
    results = await asyncio.gather(
        async_extract_keywords(my_text, top_k),
        async_extract_keywords(comp_text, top_k),
        return_exceptions=True
    )
    
    # Handle exceptions
    my_kw = results[0] if not isinstance(results[0], Exception) else []
    comp_kw = results[1] if not isinstance(results[1], Exception) else []
    
    return my_kw, comp_kw


def shutdown_executor():
    """Cleanup thread pool (call on app shutdown)."""
    _executor.shutdown(wait=True)
