"""
Scan Results Store
Persists scan results into ChromaDB for RAG retrieval and chat context.
Each scan is stored as multiple documents (one per section) for granular retrieval.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.core.vector_store import get_collection, get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "scan_results"


def _scan_doc_id(url: str, section: str) -> str:
    """Generate a deterministic document ID from URL + section."""
    key = f"{url}::{section}"
    return hashlib.md5(key.encode()).hexdigest()


def store_scan_result(
    url: str,
    scraped: Dict[str, Any],
    errors: list,
    seo_score: Dict[str, Any],
    technical: Dict[str, Any],
    performance: Optional[Dict[str, Any]] = None,
    authority: Optional[Dict[str, Any]] = None,
    ai_autofix: Optional[str] = None,
    ai_schema: Optional[str] = None,
    ai_roadmap: Optional[str] = None,
) -> str:
    """
    Store a complete scan result in ChromaDB for future RAG retrieval.
    
    Splits the scan into logical sections for granular retrieval.
    Returns a scan_id for referencing this scan.
    """
    collection = get_collection(COLLECTION_NAME)
    embeddings = get_embeddings()
    
    domain = urlparse(url).netloc
    scan_date = datetime.now(timezone.utc).isoformat()
    scan_id = hashlib.md5(f"{url}::{scan_date}".encode()).hexdigest()[:16]
    tech_stack = scraped.get("tech_stack", "Unknown")
    score_value = seo_score.get("score", 0) if isinstance(seo_score, dict) else 0
    
    base_metadata = {
        "scan_id": scan_id,
        "url": url,
        "domain": domain,
        "scan_date": scan_date,
        "tech_stack": str(tech_stack),
        "seo_score": score_value,
        "source": "scan_result",
    }
    
    documents = []
    ids = []
    metadatas = []
    
    # 1) Page overview
    title = scraped.get("title", "N/A")
    meta_desc = scraped.get("meta_description", "N/A")
    h1_list = scraped.get("h1", [])
    overview_text = (
        f"Scan SEO di {url}\n"
        f"Title: {title}\n"
        f"Meta Description: {meta_desc}\n"
        f"H1: {', '.join(h1_list) if h1_list else 'Nessuno'}\n"
        f"Stack Tecnologico: {tech_stack}\n"
        f"SEO Score: {score_value}/100\n"
        f"Data scan: {scan_date}"
    )
    documents.append(overview_text)
    ids.append(_scan_doc_id(url, "overview"))
    metadatas.append({**base_metadata, "section": "overview"})
    
    # 2) Errors summary
    if errors:
        error_lines = [f"- {str(e)[:200]}" for e in errors[:30]]
        errors_text = f"Problemi SEO rilevati su {url}:\n" + "\n".join(error_lines)
        documents.append(errors_text)
        ids.append(_scan_doc_id(url, "errors"))
        metadatas.append({**base_metadata, "section": "errors"})
    
    # 3) Technical details
    if technical:
        tech_text = (
            f"Analisi tecnica di {url}:\n"
            f"Robots.txt: {'trovato' if technical.get('robots_txt_found') else 'non trovato'}\n"
            f"Sitemap: {'trovata' if technical.get('sitemap_found') else 'non trovata'}\n"
            f"HTTPS: {'sì' if technical.get('https') else 'no'}\n"
            f"Canonical: {technical.get('canonical', 'N/A')}\n"
            f"Errori tecnici: {len(technical.get('technical_errors', []))}"
        )
        documents.append(tech_text)
        ids.append(_scan_doc_id(url, "technical"))
        metadatas.append({**base_metadata, "section": "technical"})
    
    # 4) Performance
    if performance and isinstance(performance, dict):
        perf_score = performance.get("performance_score", "N/A")
        metrics = performance.get("metrics", {})
        perf_text = (
            f"Performance di {url}:\n"
            f"Score: {perf_score}\n"
            f"LCP: {metrics.get('lcp', 'N/A')}\n"
            f"CLS: {metrics.get('cls', 'N/A')}\n"
            f"FCP: {metrics.get('fcp', 'N/A')}\n"
            f"TTFB: {metrics.get('ttfb', 'N/A')}"
        )
        documents.append(perf_text)
        ids.append(_scan_doc_id(url, "performance"))
        metadatas.append({**base_metadata, "section": "performance"})
    
    # 5) Authority
    if authority and isinstance(authority, dict):
        auth_text = (
            f"Autorità di {url}:\n"
            f"Score autorità: {authority.get('your_authority', 'N/A')}\n"
            f"Backlinks: {authority.get('backlink_count', 'N/A')}\n"
            f"Referring domains: {authority.get('referring_domains', 'N/A')}"
        )
        documents.append(auth_text)
        ids.append(_scan_doc_id(url, "authority"))
        metadatas.append({**base_metadata, "section": "authority"})
    
    # 6) AI Autofix (if generated)
    if ai_autofix and isinstance(ai_autofix, str) and len(ai_autofix) > 50:
        # Truncate to avoid huge embeddings
        autofix_text = f"Fix AI suggeriti per {url}:\n{ai_autofix[:3000]}"
        documents.append(autofix_text)
        ids.append(_scan_doc_id(url, "ai_autofix"))
        metadatas.append({**base_metadata, "section": "ai_autofix"})
    
    # 7) AI Roadmap
    if ai_roadmap and isinstance(ai_roadmap, str) and len(ai_roadmap) > 50:
        roadmap_text = f"Roadmap SEO per {url}:\n{ai_roadmap[:3000]}"
        documents.append(roadmap_text)
        ids.append(_scan_doc_id(url, "ai_roadmap"))
        metadatas.append({**base_metadata, "section": "ai_roadmap"})
    
    # Embed and upsert
    try:
        vectors = embeddings.embed_documents(documents)
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=vectors,
        )
        logger.info("✅ Stored scan result for %s: %d docs, scan_id=%s", url, len(documents), scan_id)
    except Exception as e:
        logger.error("Failed to store scan result for %s: %s", url, e)
    
    return scan_id


def query_scan_history(
    query: str,
    n_results: int = 5,
    domain: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> list[dict]:
    """
    Query scan history for relevant documents.
    
    Args:
        query: The search query.
        n_results: Number of results.
        domain: Optional domain filter.
        scan_id: Optional scan_id filter to scope to one scan.
        
    Returns:
        List of dicts with 'content', 'section', 'url', 'scan_date', 'distance'.
    """
    collection = get_collection(COLLECTION_NAME)
    
    if collection.count() == 0:
        return []
    
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    
    where_filter = None
    if scan_id and domain:
        where_filter = {"$and": [{"scan_id": scan_id}, {"domain": domain}]}
    elif scan_id:
        where_filter = {"scan_id": scan_id}
    elif domain:
        where_filter = {"domain": domain}
    
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(n_results, collection.count()),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )
    
    output = []
    if results and results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0
            output.append({
                "content": doc,
                "section": meta.get("section", ""),
                "url": meta.get("url", ""),
                "domain": meta.get("domain", ""),
                "scan_id": meta.get("scan_id", ""),
                "scan_date": meta.get("scan_date", ""),
                "seo_score": meta.get("seo_score", 0),
                "distance": dist,
            })
    
    return output


def get_latest_scan_id(domain: str) -> Optional[str]:
    """Get the most recent scan_id for a domain."""
    collection = get_collection(COLLECTION_NAME)
    
    if collection.count() == 0:
        return None
    
    results = collection.get(
        where={"domain": domain},
        include=["metadatas"],
        limit=50,
    )
    
    if not results or not results["metadatas"]:
        return None
    
    # Find the latest scan_date
    latest = None
    latest_scan_id = None
    for meta in results["metadatas"]:
        scan_date = meta.get("scan_date", "")
        if latest is None or scan_date > latest:
            latest = scan_date
            latest_scan_id = meta.get("scan_id")
    
    return latest_scan_id
