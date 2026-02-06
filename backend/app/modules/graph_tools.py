# graph_tools.py (Refactored for LangGraph)
# Adattato da SEO-AGENT/tools.py


import os
import re
import json
import logging
from collections import Counter
from datetime import datetime
import httpx
import requests
from bs4 import BeautifulSoup, Comment
from dotenv import load_dotenv

from langchain_tavily import TavilySearch
from langchain.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.llm_factory import get_shared_llm
from urllib.parse import urljoin
from app.modules.seo_technical import check_sitemap

logger = logging.getLogger(__name__)

# =========================
# CONFIGURAZIONE
# =========================

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright non trovato. Installalo con 'pip install playwright' e 'playwright install'.")

load_dotenv()

# Tool di ricerca per trovare competitor (lazy init to avoid crash if TAVILY_API_KEY not yet loaded)
_tavily_search = None

def _get_tavily_search():
    global _tavily_search
    if _tavily_search is None:
        _tavily_search = TavilySearch(max_results=5)
    return _tavily_search


# =========================
# HELPER FUNCTIONS
# =========================

# used in get_meta and get_property_meta
def _text_clean(s: str) -> str:
    return " ".join((s or "").split()).strip()

# used in extract_seo_elements_pure
def _get_meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return _text_clean(tag["content"]) if tag and tag.get("content") else None

# used in extract_seo_elements_pure
def _get_property_meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return _text_clean(tag["content"]) if tag and tag.get("content") else None

# used in analyze_competitors_pure
def _domain_from_url(url: str) -> str:
    """Returns bare domain without scheme or path."""
    try:
        return url.split("//", 1)[-1].split("/", 1)[0].lower()
    except Exception:
        return url.lower()


# ==========================================
# CORE FUNCTIONS
# ==========================================


def fetch_page_playwright(url: str) -> str:
    """Scarica pagina renderizzando JS con Playwright (Headless Chrome)."""
    # Nota: Ho rimosso il check su PLAYWRIGHT_AVAILABLE per brevità, assumendo sia gestito
    from playwright.sync_api import sync_playwright
        
    logger.info("Avvio Playwright per: %s", url)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=40000, wait_until="domcontentloaded")
            
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        return f"ERROR: Playwright failed: {str(e)}"


def fetch_page_pure(url: str) -> str:
    """
    Approccio HTTPX prioritario (molto più veloce).
    Se fallisce, prova Playwright (se disponibile).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        with httpx.Client(http2=False, follow_redirects=True, timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text

            if not html_content:
                return f"ERROR: Pagina vuota {url}"

            logger.info("Download HTTPX completato. Lunghezza: %d", len(html_content))
            return html_content
    except Exception as e:
        logger.warning("Fetch HTTPX fallito: %s", e)

        # Fallback con requests (più permissivo su alcuni siti)
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html_content = resp.text
            if html_content:
                logger.info("Download requests completato. Lunghezza: %d", len(html_content))
                return html_content
        except Exception as re:
            logger.warning("Fetch requests fallito: %s", re)

        if PLAYWRIGHT_AVAILABLE:
            logger.info("Tentativo fallback Playwright...")
            pw_html = fetch_page_playwright(url)
            if pw_html and not pw_html.startswith("ERROR:"):
                logger.info("Download Playwright completato. Lunghezza: %d", len(pw_html))
                return pw_html
            return f"ERROR: Impossibile scaricare {url}: {pw_html}"
        return f"ERROR: Impossibile scaricare {url}: {str(e)}"



def extract_seo_elements_pure(html: str, url: str, soup: BeautifulSoup, response=None) -> dict:
    """
    Estrae un set completo di dati SEO, Tecnici e di Contenuto.
    AGGIORNAMENTO: Non effettua più richieste HTTP interne. Usa html/soup forniti.
    """
    if not soup or not isinstance(soup, BeautifulSoup):
        soup = BeautifulSoup(html, "lxml")
        
    if not html or not isinstance(html, str):
        return {"error": "Invalid HTML content provided."}
    
    # Pulizia del soup (Attenzione: modifica l'oggetto soup passato per riferimento)
    for t in soup(["script", "style", "noscript", "svg", "path"]):
        t.decompose()
        
    text_content = _text_clean(soup.get_text())

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    desc = _get_meta(soup, "description")
    robots = _get_meta(soup, "robots")
    keywords = _get_meta(soup, "keywords")

    # CANONICAL
    canonical = None
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        canonical = canonical_tag.get("href")

    headings = {}
    for i in range(1, 7):
        headings[f"h{i}"] = [h.get_text().strip() for h in soup.find_all(f"h{i}") if h.get_text().strip()]

    imgs = soup.find_all("img")
    images_data = []
    for img in imgs:
        src = img.get("src", "")
        alt = img.get("alt", "").strip()
        if src:
            images_data.append({"src": src, "has_alt": bool(alt), "alt": alt})

    # PARAGRAFI
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    
    # LINKS
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if href and not href.startswith("#") and not href.startswith("javascript:"):
            links.append({
                "href": urljoin(url, href),
                "text": a.get_text(strip=True)[:100],
                "is_external": not urljoin(url, href).startswith(url.split("/")[0] + "//" + url.split("/")[2])
            })
    internal_links = [l["href"] for l in links if not l["is_external"]]
    external_links = [l["href"] for l in links if l["is_external"]]

    # FAVICON
    favicon_url = None
    favicon_tag = soup.find("link", rel=lambda v: v and "icon" in v)
    if favicon_tag:
        favicon_url = favicon_tag.get("href")

    # META VIEWPORT
    meta_viewport = False
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    if viewport_tag and viewport_tag.get("content"):
        meta_viewport = True

    # TWITTER CARD
    twitter_card = {}
    for tw_tag in soup.find_all("meta"):
        name = tw_tag.get("name")
        if name and name.startswith("twitter:"):
            twitter_card[name] = tw_tag.get("content")

    # HTML lang
    html_lang = None
    if soup.html and soup.html.get("lang"):
        html_lang = soup.html.get("lang").strip()

    # Structured data (JSON-LD)
    # NOTA: Usiamo una nuova soup temporanea sull'HTML originale perché abbiamo fatto decompose degli script sopra
    temp_soup = BeautifulSoup(html, "lxml")
    structured_data_present = False
    for s in temp_soup.find_all("script", attrs={"type": "application/ld+json"}):
        if s.string and s.string.strip():
            structured_data_present = True
            break
            
    # COMPRESSIONE (Richiede l'oggetto response passato come argomento opzionale)
    compression = False
    if response and hasattr(response, 'headers'):
        encoding = response.headers.get("Content-Encoding", "").lower()
        if "gzip" in encoding or "br" in encoding or "deflate" in encoding:
            compression = True

    og_data = {
        "og:title": _get_property_meta(soup, "og:title"),
        "og:description": _get_property_meta(soup, "og:description"),
        "og:image": _get_property_meta(soup, "og:image"),
    }

    scripts = len(temp_soup.find_all("script")) # Usiamo temp_soup perché soup ha script rimossi
    
    tech_stack = []
    html_raw = html.lower()
    if "/_next/" in html_raw: tech_stack.append("Next.js")
    if "wp-content" in html_raw: tech_stack.append("WordPress")
    if "shopify" in html_raw: tech_stack.append("Shopify")
    if "wix" in html_raw: tech_stack.append("Wix")
    if "bootstrap" in html_raw: tech_stack.append("Bootstrap")
    if "jquery" in html_raw: tech_stack.append("jQuery")

    # Check for sitemap
    sitemap_data = check_sitemap(url)
    sitemap_url = sitemap_data.get("sitemap_url")

    result = {
        "url": url,
        "title": title,
        "meta_description": desc,
        "robots": robots,
        "keywords": keywords,
        "canonical": canonical,
        "favicon": favicon_url,
        "sitemap_url": sitemap_url,
        "headings": headings,
        "meta_viewport": meta_viewport,
        "word_count": len(text_content.split()),
        "text_ratio": len(text_content) / len(html) if len(html) > 0 else 0,
        "images": images_data,
        "paragraphs": paragraphs,
        "links": links,
        "twitter_card": twitter_card,
        "html_lang": html_lang,
        "structured_data_present": structured_data_present,
        "compression": compression,
        "images_count": len(images_data),
        "missing_alt_count": sum(1 for i in images_data if not i['has_alt']),
        "links_internal": len(internal_links),
        "links_external": len(external_links),
        "social_tags": og_data,
        "tech_stack": ", ".join(tech_stack) if tech_stack else "HTML/Custom",
        "scripts_count": scripts,
        "page_size_kb": len(html) / 1024,
        "has_https": url.startswith("https"),
        "text_sample": text_content[:2000]
    }
    logger.debug("[extract_seo_elements_pure] Dati estratti: %s", json.dumps(result, ensure_ascii=False, indent=2))
    return result



def detect_seo_issues_pure(seo_data: dict) -> list:
    """
    Delegated to the unified detection module to avoid code duplication.
    This wrapper maintains backward compatibility for graph_tools callers.
    """
    from app.modules.seo_detection_unified import detect_seo_issues_unified
    return detect_seo_issues_unified(seo_data)


def generate_fixes_pure(
    issues: list,
    user_url: str = "https://example.com",
    text_sample: str = "",
    tech_stack: str = "HTML/Custom",
) -> list:
    """Genera fix contestuali per i problemi usando l'LLM, adattando il codice allo stack rilevato."""
    if not issues:
        return []

    llm = get_shared_llm()
    issues_str = json.dumps(issues, indent=2)
    safe_sample = text_sample[:500].replace("\n", " ") if text_sample else "Nessun testo estratto."

    system_prompt = f"""Sei un Esperto SEO Tecnico e Sviluppatore Web Senior.

CONTESTO SITO:
- URL Reale: {user_url}
- Stack / Framework: {tech_stack}
- Estratto Contenuto: "{safe_sample}..."

TASK:
Per OGNI problema fornito, genera una soluzione tecnica dettagliata.

REGOLE CRITICHE:
1. Usa SEMPRE l'URL reale "{user_url}" nei tag canonical, og:url, ecc.
2. NON usare mai "www.esempio.com" o "tuosito.com".
3. Inventa ALT text realistici basati sul testo estratto.
4. Adatta il codice allo stack dichiarato ({tech_stack}):
   - Next.js/React: JSX/TSX con next/head o export metadata.
   - WordPress: snippet PHP per functions.php con hook.
   - Shopify/Liquid: blocchi Liquid + HTML/CSS.
   - Vue/Nuxt: SFC (template+script) o composables.
   - Altrimenti HTML/CSS/JS vanilla.
5. FORNISCI CODICE COMPLETO copia-incollabile per ogni problema.

Rispondi SOLO con un array JSON valido. Ogni elemento deve avere:
- "issue_id": stringa, copia l'id del problema
- "explanation": stringa, spiegazione tecnica (max 2 frasi)
- "code_snippet": stringa, codice HTML/JS/Config corretto

ESEMPIO FORMATO (Array JSON):
[
  {{"issue_id": "missing_meta", "explanation": "La meta description mancante riduce il CTR.", "code_snippet": "<meta name=\\"description\\" content=\\"...\\">"}}
]

IMPORTANTE: Rispondi SOLO con l'array JSON. Nessun testo prima o dopo. Nessun markdown. Solo JSON puro."""

    user_prompt = f"PROBLEMI RILEVATI:\n{issues_str}\n\nGenera i fix ora come array JSON puro."

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw = response.content.strip()

        # Try to extract JSON from response (handle markdown code blocks)
        result = _extract_json_list(raw)
        if result is not None:
            return result

        logger.error("Could not parse fixes JSON. Raw response (first 500): %s", raw[:500])
        return [{
            "issue_id": "ai_parse_error",
            "explanation": "L'AI ha generato una risposta non parsabile. Riprova la scansione.",
            "code_snippet": "",
        }]

    except Exception as e:
        logger.error("Exception in generate_fixes_pure: %s", e)
        return [{
            "issue_id": "ai_error",
            "explanation": f"Errore generazione fix: {str(e)[:200]}",
            "code_snippet": ""
        }]


def _extract_json_list(text: str) -> list | None:
    """
    Robust JSON list extraction from LLM output.
    Handles markdown code blocks, leading text, trailing text.
    """
    # 1) Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

    # 2) Try direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # 3) Find the outermost [ ... ] bracket pair
    start = cleaned.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "[":
                depth += 1
            elif cleaned[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(cleaned[start:i+1])
                        if isinstance(parsed, list):
                            return parsed
                    except json.JSONDecodeError:
                        break
                    break

    # 4) Try to find individual JSON objects with regex
    objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned)
    if objects:
        results = []
        for obj_str in objects:
            try:
                obj = json.loads(obj_str)
                if isinstance(obj, dict) and "issue_id" in obj:
                    results.append(obj)
            except json.JSONDecodeError:
                continue
        if results:
            return results

    return None


def analyze_security_pure(html: str) -> list:
    """Analizza l'HTML alla ricerca di API Key esposte e problemi di sicurezza."""
    issues = []
    
    patterns = {
        "Google Maps API": r"AIza[0-9A-Za-z-_]{35}",
        "Mailchimp API": r"[0-9a-f]{32}-us[0-9]{1,2}",
        "Stripe Secret": r"sk_live_[0-9a-zA-Z]+",
        "AWS Access Key": r"AKIA[0-9A-Z]{16}"
    }
    
    for name, pattern in patterns.items():
        found = re.findall(pattern, html)
        if found:
            issues.append({
                "id": "security_leak", 
                "category": "security", 
                "description": f"⚠️ GRAVE: Esposta chiave {name}. Rimuovila immediatamente dal frontend!",
                "penalty": 50
            })
            
    if "https://" not in html.lower() and "http://" in html.lower():
        issues.append({"id": "mixed_content", "category": "security", "description": "Rilevati link HTTP non sicuri (Mixed Content)."})
         
    return issues


def analyze_competitors_pure(keyword: str, user_url: str, limit: int = 3, seo_data: dict | None = None) -> list:
    """Cerca competitor organici usando Tavily con fallback su Google Serper.
    
    Uses scraped page data (title, meta_description, keywords) to build
    sector-specific search queries instead of generic "competitor" lookups.
    """
    import requests

    if not keyword:
        return []

    base_domain = _domain_from_url(user_url)

    results_data = []
    analyzed_urls = []
    analyzed_domains = set([base_domain])

    def is_new_competitor(url: str) -> bool:
        domain = _domain_from_url(url)
        if not domain or domain in analyzed_domains:
            return False
        analyzed_domains.add(domain)
        analyzed_urls.append(url)
        return True

    def _extract_sector_keywords(seo: dict) -> str:
        """Extract meaningful sector terms from page metadata."""
        parts = []
        title = (seo.get("title") or "").strip()
        if title:
            # Use first meaningful chunk of title (skip brand suffixes after |/-)
            clean_title = title.split("|")[0].split(" - ")[0].strip()
            parts.append(clean_title)

        meta_desc = (seo.get("meta_description") or "").strip()
        if meta_desc:
            # Take first sentence of meta description
            first_sentence = meta_desc.split(".")[0].strip()
            if len(first_sentence) > 15:
                parts.append(first_sentence)

        meta_kw = (seo.get("keywords") or "").strip()
        if meta_kw:
            # Use first 3 meta keywords
            kw_list = [k.strip() for k in meta_kw.split(",") if k.strip()]
            parts.append(" ".join(kw_list[:3]))

        return " | ".join(parts) if parts else ""

    def build_queries(seed: str, seo: dict | None) -> list[str]:
        """Build multiple sector-specific queries from page context."""
        queries = []
        sector_info = _extract_sector_keywords(seo) if seo else ""

        if sector_info:
            # Primary: sector-aware query using actual page content
            queries.append(f"{sector_info} migliori alternative concorrenti")
            # Secondary: use the seed keyword + sector context
            title_clean = (seo.get("title") or "").split("|")[0].split(" - ")[0].strip()
            if title_clean and title_clean.lower() != seed.lower():
                queries.append(f"{title_clean} competitors top sites")
        
        # Fallback: use the seed keyword with a sector-aware suffix
        seed_clean = " ".join(seed.split())
        queries.append(f"siti simili a {seed_clean} stesse funzionalità")

        return queries
    
    try:
        queries = build_queries(keyword, seo_data)
        for query in queries:
            if len(results_data) >= limit:
                break
            logger.debug("Trying Tavily for '%s'...", query)
            tavily_results = _get_tavily_search().invoke(query)
        
            if isinstance(tavily_results, dict):
                tavily_results = tavily_results.get("results", [])
                
            if tavily_results and isinstance(tavily_results, list):
                for res in tavily_results:
                    url = res.get("url", "N/A")
                    content = res.get("content") or res.get("raw_content") or ""
                    
                    if not is_new_competitor(url):
                        continue
                    
                    results_data.append({
                        "source": "tavily",
                        "name": res.get("title", "No Title"),
                        "url": url,
                        "snippet": content[:200] + "..."
                    })
            
        if results_data:
            logger.info("Tavily success! Found %d results.", len(results_data))
    
    except Exception as e:
        logger.warning("Tavily failed: %s", e)

    if not results_data:
        logger.info("Switching to Google Serper Direct Call...")
        api_key = os.getenv("SERPER_API_KEY")
        
        if api_key:
            try:
                # Build a sector-aware Serper query too
                serper_query = keyword
                if seo_data:
                    title = (seo_data.get("title") or "").split("|")[0].split(" - ")[0].strip()
                    meta_kw = (seo_data.get("keywords") or "").strip()
                    if meta_kw:
                        kw_parts = [k.strip() for k in meta_kw.split(",") if k.strip()][:2]
                        serper_query = f"{title} {' '.join(kw_parts)} alternative"
                    elif title:
                        serper_query = f"{title} concorrenti alternativi"
                
                url = "https://google.serper.dev/search"
                payload = json.dumps({
                    "q": serper_query,
                    "gl": "it",
                    "hl": "it",
                    "num": 5
                })
                headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
                
                response = requests.post(url, headers=headers, data=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                for res in data.get("organic", []):
                    link = res.get("link")
                    if not link or not is_new_competitor(link): 
                        continue
                    results_data.append({
                        "source": "serper",
                        "name": res.get("title", "No Title"),
                        "url": link,
                        "snippet": res.get("snippet", "")
                    })
                logger.info("Serper success! Found %d results.", len(results_data))
                
            except Exception as e:
                logger.warning("Serper failed: %s", e)
    return results_data[:limit]


def calculate_seo_score(issues: list) -> int:
    """Calcola un punteggio da 0 a 100 basato sulla gravità dei problemi."""
    score = 100
    for i in issues:
        penalty = i.get("penalty", 5)
        cat = i.get("category", "").lower()
        if "critical" in cat: 
            penalty = 20
        elif "security" in cat: 
            penalty = 30
        elif "technical" in cat: 
            penalty = 10
        elif "content" in cat: 
            penalty = 5
        
        score -= penalty
        
    return max(0, score)
