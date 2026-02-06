import logging
import random
import time
from typing import Dict, Any

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

from app.modules.graph_tools import fetch_page_playwright
from app.modules.graph_tools import extract_seo_elements_pure

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# TTL Cache for scraped URLs — avoids hammering the same site within a session
# ═══════════════════════════════════════════════════════════════════════════════

_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_MAX_SIZE = 50

_scrape_cache: Dict[str, Dict[str, Any]] = {}
# Structure: { url: { "data": {...}, "ts": float } }


def _cache_get(url: str) -> dict | None:
    """Return cached scrape result if still valid, else None."""
    entry = _scrape_cache.get(url)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL_SECONDS:
        logger.info("Cache HIT for %s", url)
        return entry["data"]
    # Expired or missing
    if entry:
        del _scrape_cache[url]
    return None


def _cache_set(url: str, data: dict) -> None:
    """Store scrape result in cache. Evicts oldest if over limit."""
    if len(_scrape_cache) >= _CACHE_MAX_SIZE:
        # Evict oldest entry
        oldest_url = min(_scrape_cache, key=lambda u: _scrape_cache[u]["ts"])
        del _scrape_cache[oldest_url]
    _scrape_cache[url] = {"data": data, "ts": time.time()}


def clear_scrape_cache() -> int:
    """Clear the scrape cache. Returns number of entries cleared."""
    count = len(_scrape_cache)
    _scrape_cache.clear()
    return count

# Rotating User-Agent pool to reduce blocking
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def _get_random_ua() -> str:
    return random.choice(_USER_AGENTS)


def smart_scrape_url(url: str):
    """
    Scraper unificato: usa requests+BS4, poi Playwright solo se mancano dati chiave.
    Risultati cached per 5 minuti per evitare richieste duplicate.
    """
    # Check cache first
    cached = _cache_get(url)
    if cached is not None:
        return cached

    # Prima pass: scraping classico con requests
    data = scrape_url(url)
    data["scraper_used"] = "requests"
    
    # Se c'è errore di connessione o manca JSON-LD, prova Playwright
    if data.get("error") or not data.get("structured_data_present"):
        html = fetch_page_playwright(url)
        
        if html and not html.startswith("ERROR"):
            # Creiamo una NUOVA soup dall'HTML renderizzato
            soup = BeautifulSoup(html, "lxml")
            
            # Ricalcoliamo TUTTO usando i dati renderizzati
            data = extract_seo_elements_pure(html, url, soup)
            data["html_content"] = html
            data["scraper_used"] = "playwright"
    
    # Cache successful results (don't cache errors)
    if not data.get("error"):
        _cache_set(url, data)

    return data


def scrape_url(url: str, max_retries: int = 2):
    """Scrape a URL with retry logic and User-Agent rotation."""
    headers = {
        "User-Agent": _get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    }
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "lxml")

            data = extract_seo_elements_pure(html, url, soup)
            data["html_content"] = html
            return data

        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(f"Timeout scraping {url} (attempt {attempt + 1}/{max_retries + 1})")
            headers["User-Agent"] = _get_random_ua()  # Rotate UA on retry
        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(f"Connection error scraping {url}: {e}")
            break  # Don't retry connection errors
        except requests.exceptions.HTTPError as e:
            last_error = e
            logger.warning(f"HTTP error scraping {url}: {e}")
            break  # Don't retry HTTP errors (4xx/5xx)
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error scraping {url}: {type(e).__name__}: {e}")
            break
    
    return {"error": f"Impossibile raggiungere il sito: {str(last_error)[:200]}"}
