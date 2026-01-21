import xml.etree.ElementTree as ET

def analyze_sitemap(sitemap_url: str, max_urls: int = 10000, timeout: int = 10) -> dict:
    """
    Scarica e analizza ricorsivamente una sitemap.xml (anche sitemap index).
    Restituisce:
      - urls: lista di URL estratti
      - invalid: lista di URL non validi o con status >=400
      - errors: lista errori
      - is_index: True se sitemap index
    """
    import requests
    from urllib.parse import urljoin, urlparse
    urls = set()
    valid_urls = set()
    skipped_urls = []
    invalid = []
    errors = []
    visited = set()
    max_depth = 5

    def _normalize_url(base, u):
        if not u:
            return None
        u = u.strip()
        if not u:
            return None
        parsed = urlparse(u)
        if not parsed.scheme:
            # relative URL
            u = urljoin(base, u)
        return u

    def _fetch_and_parse(url):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200:
                errors.append(f"HTTP {resp.status_code} for {url}")
                return None
            return ET.fromstring(resp.content)
        except Exception as e:
            errors.append(f"{url}: {str(e)}")
            return None

    def _analyze(url, depth=0):
        if url in visited or len(urls) >= max_urls or depth > max_depth:
            if depth > max_depth:
                errors.append(f"Profondità massima superata su {url}")
            return
        visited.add(url)
        root = _fetch_and_parse(url)
        if root is None:
            return
        tag = root.tag.lower()
        if tag.endswith('sitemapindex'):
            for sm in root.findall('.//{*}sitemap/{*}loc'):
                child_url = _normalize_url(url, sm.text)
                if child_url:
                    _analyze(child_url, depth+1)
        elif tag.endswith('urlset'):
            for loc in root.findall('.//{*}url/{*}loc'):
                u = _normalize_url(url, loc.text)
                if u:
                    urls.add(u)
        else:
            errors.append(f"Formato non riconosciuto: {url}")

    _analyze(sitemap_url)

    # Filtra duplicati e normalizza
    urls = list(urls)
    # Validazione: controlla status code degli URL estratti (sample max 100)
    import random
    sample = urls[:100] if len(urls) > 100 else urls
    for u in sample:
        try:
            r = requests.head(u, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:
                invalid.append({"url": u, "status": r.status_code})
                skipped_urls.append({"url": u, "reason": f"Status {r.status_code}"})
            else:
                valid_urls.add(u)
        except Exception as e:
            invalid.append({"url": u, "error": str(e)})
            skipped_urls.append({"url": u, "reason": str(e)})

    return {
        "sitemap_url": sitemap_url,
        "is_index": any(x.endswith('sitemapindex') for x in [ET.ElementTree(_fetch_and_parse(sitemap_url)).getroot().tag.lower()]),
        "total_urls": len(urls),
        "urls": list(valid_urls),
        "invalid": invalid,
        "skipped_urls": skipped_urls,
        "errors": errors
    }
# app/modules/seo_technical.py
"""
Modulo Technical SEO checks (MVP).
Riceve il dict 'scraped' dallo scraper e restituisce:
  - technical_flags: dict con info utili (robots_found, sitemap_found, https, status_code...)
  - technical_errors: lista di error dict (stesso formato del detector)
"""

import requests
from urllib.parse import urlparse, urljoin
from typing import Dict, List

REQUEST_TIMEOUT = 6

def _safe_head(url: str):
    try:
        r = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        # include resolved URL so callers can detect scheme after redirects
        return {"status_code": r.status_code, "headers": dict(r.headers), "url": r.url}
    except Exception as e:
        return {"error": str(e)}

def _safe_get(url: str):
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return {"status_code": r.status_code, "text": r.text, "headers": dict(r.headers), "url": r.url}
    except Exception as e:
        return {"error": str(e)}

def check_robots(url: str) -> Dict:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    res = _safe_get(robots_url)
    ok = False
    contains_sitemap = False
    if res.get("status_code") == 200 and isinstance(res.get("text"), str):
        ok = True
        if "Sitemap:" in res["text"] or "sitemap:" in res["text"]:
            contains_sitemap = True
    return {"robots_url": robots_url, "robots_found": ok, "robots_text": res.get("text") if ok else None, "robots_error": res.get("error"), "robots_contains_sitemap": contains_sitemap}

def check_sitemap(url: str) -> Dict:
    parsed = urlparse(url)
    # common sitemap locations
    candidates = [
        f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
        f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml"
    ]
    for s in candidates:
        res = _safe_head(s)
        if res.get("status_code") == 200:
            return {"sitemap_url": s, "sitemap_found": True}
    return {"sitemap_url": None, "sitemap_found": False}

def check_https(url: str) -> Dict:
    parsed = urlparse(url)
    # consider original scheme OR the scheme of the resolved URL after HEAD redirects
    head_res = _safe_head(url)
    resolved = head_res.get("url")
    resolved_scheme_https = False
    try:
        if resolved:
            resolved_scheme_https = urlparse(resolved).scheme.lower() == "https"
    except Exception:
        resolved_scheme_https = False

    https_ok = parsed.scheme.lower() == "https" or resolved_scheme_https
    return {"https": https_ok, "status_code": head_res.get("status_code"), "head_error": head_res.get("error"), "resolved_url": resolved}

def check_meta_robots(scraped: Dict) -> Dict:
    # prefer the scraped meta_robots if present
    meta_robots = scraped.get("meta_robots")
    # if not present, try to parse headers if available
    return {"meta_robots": meta_robots}

def check_canonical(scraped: Dict, url: str) -> Dict:
    canonical = scraped.get("canonical")
    if not canonical:
        # missing canonical
        return {"canonical": None, "canonical_ok": False}
    # basic validation: same host or absolute
    try:
        parsed_self = urlparse(url)
        parsed_can = urlparse(canonical)
        ok = True
        # if canonical relative -> ok
        if not parsed_can.netloc:
            ok = True
        else:
            ok = parsed_self.netloc == parsed_can.netloc
        return {"canonical": canonical, "canonical_ok": ok}
    except Exception:
        return {"canonical": canonical, "canonical_ok": False}

def security_headers_from_response_headers(headers: Dict) -> Dict:
    # controlla solo alcuni header importanti
    return {
        "x_frame_options": bool(headers.get("X-Frame-Options") or headers.get("x-frame-options")),
        "content_security_policy": bool(headers.get("Content-Security-Policy") or headers.get("content-security-policy")),
        "x_content_type_options": bool(headers.get("X-Content-Type-Options") or headers.get("x-content-type-options")),
        "referrer_policy": bool(headers.get("Referrer-Policy") or headers.get("referrer-policy"))
    }

def run_technical_checks(scraped: Dict, url: str) -> Dict:
    """
    Restituisce:
      - technical_flags: dict (robots_found, sitemap_found, canonical_ok, https, meta_viewport_present, open_graph_present, structured_data_present)
      - technical_errors: lista di dict error (stesso schema)
    """
    tech_flags = {}
    tech_errors = []

    # robots
    robots_res = check_robots(url)
    tech_flags.update({
        "robots_txt_found": robots_res.get("robots_found", False),
        "robots_contains_sitemap": robots_res.get("robots_contains_sitemap", False),
    })
    if not robots_res.get("robots_found"):
        tech_errors.append({
            "id": "missing_robots",
            "category": "technical",
            "severity": "notice",
            "penalty": 5,
            "difficulty": "easy",
            "description": "robots.txt non trovato.",
            "suggested_fix": "Aggiungi un file robots.txt per gestire indicizzazione e sitemaps."
        })


    # sitemap
    import logging
    logger = logging.getLogger(__name__)
    sitemap_res = check_sitemap(url)
    logger.info(f"[SITEMAP] check_sitemap result: {sitemap_res}")
    # If not found directly, check robots.txt for 'Sitemap:' directive and verify the candidate URLs
    if not sitemap_res.get("sitemap_found"):
        robots_text = robots_res.get("robots_text")
        if robots_text:
            for line in robots_text.splitlines():
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip().lower() == "sitemap":
                    candidate = parts[1].strip()
                    # make absolute if relative path
                    parsed = urlparse(url)
                    if candidate.startswith("/"):
                        candidate = f"{parsed.scheme}://{parsed.netloc}{candidate}"
                    head = _safe_head(candidate)
                    logger.info(f"[SITEMAP] robots.txt candidate: {candidate}, HEAD: {head}")
                    if head.get("status_code") == 200:
                        sitemap_res = {"sitemap_url": candidate, "sitemap_found": True}
                        break

    # Fallback: prova sempre /sitemap.xml se non trovato
    if not sitemap_res.get("sitemap_found"):
        parsed = urlparse(url)
        fallback = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        head = _safe_head(fallback)
        logger.info(f"[SITEMAP] Fallback /sitemap.xml HEAD: {head}")
        if head.get("status_code") == 200:
            sitemap_res = {"sitemap_url": fallback, "sitemap_found": True}

    tech_flags["sitemap_found"] = sitemap_res.get("sitemap_found", False)
    tech_flags["sitemap_url"] = sitemap_res.get("sitemap_url")

    if not sitemap_res.get("sitemap_found"):
        tech_errors.append({
            "id": "missing_sitemap",
            "category": "technical",
            "severity": "notice",
            "penalty": 5,
            "difficulty": "easy",
            "description": "sitemap.xml non trovato nelle posizioni comuni o dichiarato nel robots.txt.",
            "suggested_fix": "Genera una sitemap.xml e rendila accessibile o aggiungi direttiva Sitemap: nel robots.txt."
        })

    # https + status
    https_res = check_https(url)
    tech_flags["https"] = https_res.get("https", False)
    tech_flags["status_code"] = https_res.get("status_code")
    if https_res.get("https") is False:
        tech_errors.append({
            "id": "not_https",
            "category": "security",
            "severity": "error",
            "penalty": 25,
            "difficulty": "easy",
            "description": "La URL non usa HTTPS.",
            "suggested_fix": "Abilita HTTPS con certificato valido (Let's Encrypt)."
        })
    if https_res.get("status_code") and int(https_res.get("status_code")) >= 400:
        tech_errors.append({
            "id": "http_error_status",
            "category": "technical",
            "severity": "error",
            "penalty": 20,
            "difficulty": "medium",
            "description": f"Status HTTP della pagina {https_res.get('status_code')}.",
            "suggested_fix": "Controlla le risposte server e risolvi errori 4xx/5xx."
        })

    # meta robots
    meta_robots = check_meta_robots(scraped).get("meta_robots")
    tech_flags["meta_robots"] = meta_robots
    if meta_robots and "noindex" in meta_robots.lower():
        tech_errors.append({
            "id": "noindex_meta",
            "category": "technical",
            "severity": "error",
            "penalty": 25,
            "difficulty": "easy",
            "description": f"Meta robots contiene 'noindex': {meta_robots}",
            "suggested_fix": "Rimuovi noindex se desideri che la pagina sia indicizzata."
        })

    # canonical
    canonical_res = check_canonical(scraped, url)
    tech_flags.update(canonical_res)
    if not canonical_res.get("canonical_ok"):
        tech_errors.append({
            "id": "canonical_problem",
            "category": "technical",
            "severity": "warning",
            "penalty": 10,
            "difficulty": "medium",
            "description": "Canonical assente o non coerente con la URL corrente.",
            "suggested_fix": "Assicurati che il canonical punti alla versione corretta della pagina."
        })


    # viewport
    tech_flags["meta_viewport"] = bool(scraped.get("meta_viewport"))
    if not tech_flags["meta_viewport"]:
        tech_errors.append({
            "id": "missing_viewport",
            "category": "ux",
            "severity": "warning",
            "penalty": 6,
            "difficulty": "easy",
            "description": "Meta viewport mancante (problema mobile).",
            "suggested_fix": 'Aggiungi <meta name="viewport" content="width=device-width, initial-scale=1">'
        })

    # favicon
    tech_flags["favicon"] = bool(scraped.get("favicon"))
    if not tech_flags["favicon"]:
        tech_errors.append({
            "id": "missing_favicon",
            "category": "ux",
            "severity": "notice",
            "penalty": 2,
            "difficulty": "easy",
            "description": "Favicon non trovata.",
            "suggested_fix": 'Aggiungi <link rel="icon" href="/favicon.ico"> nell\'head.'
        })

    # open graph
    og = scraped.get("open_graph")
    tech_flags["open_graph_present"] = bool(og and isinstance(og, dict) and og.get("og:title"))
    if not tech_flags["open_graph_present"]:
        tech_errors.append({
            "id": "missing_open_graph",
            "category": "onpage",
            "severity": "notice",
            "penalty": 4,
            "difficulty": "easy",
            "description": "Open Graph non presente o incompleto.",
            "suggested_fix": "Aggiungi og:title e og:description per migliorare condivisione social."
        })

    # twitter card
    tw = scraped.get("twitter_card")
    tech_flags["twitter_card_present"] = bool(tw and isinstance(tw, dict) and (tw.get("twitter:card") or tw.get("twitter:title")))
    if not tech_flags["twitter_card_present"]:
        tech_errors.append({
            "id": "missing_twitter_card",
            "category": "onpage",
            "severity": "notice",
            "penalty": 2,
            "difficulty": "easy",
            "description": "Twitter Card non trovata o incompleta.",
            "suggested_fix": "Aggiungi meta tag twitter:card e twitter:title per ottimizzare la condivisione su Twitter."
        })

    # structured data fast check (schema)
    tech_flags["structured_data_present"] = bool(scraped.get("structured_data_present"))
    if not tech_flags["structured_data_present"]:
        tech_errors.append({
            "id": "missing_schema",
            "category": "technical",
            "severity": "notice",
            "penalty": 6,
            "difficulty": "medium",
            "description": "Nessun JSON-LD / schema.org rilevato.",
            "suggested_fix": "Aggiungi JSON-LD per articolo/prodotto/localBusiness."
        })

    # compressione
    tech_flags["compression"] = bool(scraped.get("compression"))
    if not tech_flags["compression"]:
        tech_errors.append({
            "id": "missing_compression",
            "category": "performance",
            "severity": "notice",
            "penalty": 2,
            "difficulty": "easy",
            "description": "La compressione (gzip/br) non è abilitata nella risposta.",
            "suggested_fix": "Abilita la compressione GZIP o Brotli sul server web per migliorare la velocità."
        })

    # security headers sample: if the response headers were passed in scraped (prefer), check them
    headers = scraped.get("response_headers") or {}
    sec = security_headers_from_response_headers(headers)
    tech_flags["security_headers"] = sec
    if not sec.get("x_frame_options") or not sec.get("x_content_type_options"):
        tech_errors.append({
            "id": "missing_security_headers",
            "category": "security",
            "severity": "notice",
            "penalty": 4,
            "difficulty": "easy",
            "description": "Header di sicurezza (X-Frame-Options / X-Content-Type-Options) mancanti.",
            "suggested_fix": "Imposta header di sicurezza per proteggere il sito."
        })

    return {"technical_flags": tech_flags, "technical_errors": tech_errors}
