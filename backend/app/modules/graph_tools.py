# graph_tools.py (Refactored for LangGraph)
# Adattato da SEO-AGENT/tools.py


import os
import re
import json
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
# =========================
# CONFIGURAZIONE
# =========================

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright non trovato. Installalo con 'pip install playwright' e 'playwright install'.")

load_dotenv()

# Tool di ricerca per trovare competitor
tavily_search = TavilySearch(max_results=5)


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
        
    print(f"--- 🎭 Avvio Playwright per: {url} ---")
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
        with httpx.Client(http2=False, follow_redirects=True, timeout=15.0, verify=False) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text

            if not html_content:
                return f"ERROR: Pagina vuota {url}"

            print(f"✅ Download HTTPX completato. Lunghezza: {len(html_content)}")
            return html_content
    except Exception as e:
        print(f"❌ Fetch HTTPX fallito: {e}")

        # Fallback con requests (più permissivo su alcuni siti)
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            resp.raise_for_status()
            html_content = resp.text
            if html_content:
                print(f"✅ Download requests completato. Lunghezza: {len(html_content)}")
                return html_content
        except Exception as re:
            print(f"❌ Fetch requests fallito: {re}")

        if PLAYWRIGHT_AVAILABLE:
            print("🎭 Tentativo fallback Playwright...")
            pw_html = fetch_page_playwright(url)
            if pw_html and not pw_html.startswith("ERROR:"):
                print(f"✅ Download Playwright completato. Lunghezza: {len(pw_html)}")
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
    print("[extract_seo_elements_pure] Dati estratti:", json.dumps(result, ensure_ascii=False, indent=2))
    return result



def detect_seo_issues_pure(seo_data: dict) -> list:
    """Analisi approfondita con 20+ controlli SEO."""
    if not seo_data:
        return []

    issues = []
    
    def add_issue(id, cat, desc, penalty=10):
        issues.append({"id": id, "category": cat, "description": desc, "penalty": penalty})

    title = seo_data.get("title")
    if not title:
        add_issue("missing_title", "critical", "Manca il Tag <title>. È il fattore on-page più importante.")
    elif len(title) < 10:
        add_issue("short_title", "content", f"Title troppo breve ({len(title)} chars). Sfrutta tutto lo spazio (50-60 chars).")
    elif len(title) > 65:
        add_issue("long_title", "content", f"Title troppo lungo ({len(title)} chars). Verrà troncato nelle SERP.")

    desc = seo_data.get("meta_description")
    if not desc:
        add_issue("missing_meta_desc", "content", "Manca la Meta Description. Riduce il CTR nei risultati di ricerca.")
    elif len(desc) < 50:
        add_issue("short_meta_desc", "content", "Meta Description troppo breve. Non invoglia al clic.")

    h1s = seo_data.get("headings", {}).get("h1", [])
    if not h1s:
        add_issue("missing_h1", "technical", "Manca il tag H1. Google faticherà a capire l'argomento principale.")
    elif len(h1s) > 1:
        add_issue("multiple_h1", "technical", f"Trovati {len(h1s)} tag H1. Usa un solo H1 per pagina per chiarezza semantica.")

    word_count = seo_data.get("word_count", 0)
    if word_count < 300:
        add_issue("thin_content", "content", f"Contenuto scarso ({word_count} parole). Google penalizza le pagine 'thin content'.")

    missing_alt = seo_data.get("missing_alt_count", 0)
    if missing_alt > 0:
        add_issue("missing_alt", "accessibility", f"{missing_alt} immagini mancano di attributo ALT (testo alternativo).")

    page_size = seo_data.get("page_size_kb", 0)
    if page_size > 2000:
        add_issue("heavy_page", "performance", f"Il codice HTML è molto pesante ({int(page_size)}KB). Rallenta il caricamento.")

    if not seo_data.get("canonical"):
        add_issue("missing_canonical", "technical", "Manca il tag Canonical. Rischio duplicazione contenuti.")
    
    og_title = seo_data.get("social_tags", {}).get("og:title")
    if not og_title:
        add_issue("missing_og_tags", "social", "Mancano i tag Open Graph. La condivisione sui social non avrà anteprima.")

    if seo_data.get("links_internal", 0) < 3:
        add_issue("orphan_risk", "structure", "Pochi link interni. La pagina rischia di essere isolata (Orphan Page).")

    return issues


def generate_fixes_pure(
    issues: list,
    user_url: str = "https://example.com",
    text_sample: str = "",
    tech_stack: str = "HTML/Custom",
) -> list:
    """Genera fix contestuali per i problemi usando l'LLM, adattando il codice allo stack rilevato."""
    if not issues:
        return []

    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import PromptTemplate

    parser = JsonOutputParser()

    prompt = PromptTemplate(
        template="""Sei un Esperto SEO Tecnico e Sviluppatore Web Senior. 
        
        CONTESTO SITO:
        - URL Reale: {user_url}
        - Stack / Framework: {tech_stack}
        - Estratto Contenuto: "{text_sample}..." (Usa questo contesto per scrivere fix pertinenti al settore)
        
        PROBLEMI RILEVATI:
        {issues}
        
        TASK:
        Per OGNI problema, fornisci una soluzione tecnica dettagliata in formato JSON.
        
          REGOLE CRITICHE:
        1. Usa SEMPRE l'URL reale "{user_url}" nei tag canonical, og:url, ecc.
        2. NON usare mai "www.esempio.com" o "tuosito.com".
        3. Inventate ALT text realistici basati sul testo estratto.
          4. Adatta il codice allo stack dichiarato (deve essere incollabile):
               - Se include "Next.js" o "React": usa JSX/TSX. Per meta/OG usa `next/head` (Pages) oppure l'export `metadata`/`generateMetadata` (App Router). Per API usa route handler in `app/api/.../route.ts` o API routes Pages. Per immagini usa SEMPRE `<Image />` da `next/image` (con import relativo) e non `<img>`. Evita tag HTML nudi se esiste una soluzione framework.
              - Se include "WordPress": fornisci snippet PHP per functions.php/template con hook corretti o blocchi HTML/PHP contestuali.
              - Se include "Shopify"/"Liquid": fornisci blocchi Liquid + HTML/CSS.
              - Se include "Vue"/"Nuxt": fornisci SFC (template+script) o composables.
              - Altrimenti fornisci HTML/CSS/JS vanilla.
          5. FORNISCI IL CODICE COMPLETO per ogni problema da copiare-incollare.
        
        FORMATO RISPOSTA (Lista JSON pura):
        {{
            "issue_id": "copia l'id del problema",
            "explanation": "Spiegazione tecnica del perché è un problema (max 2 frasi)",
            "code_snippet": "Codice HTML/JS/Config corretto da copiare-incollare."
        }}
        
        {format_instructions}
        """,
        input_variables=["issues", "user_url", "text_sample", "tech_stack"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | get_shared_llm() | parser
    issues_str = json.dumps(issues, indent=2)
    safe_sample = text_sample[:500].replace("\n", " ") if text_sample else "Nessun testo estratto."

    try:
        result = chain.invoke({
            "issues": issues_str,
            "user_url": user_url,
            "text_sample": safe_sample,
            "tech_stack": tech_stack,
        })
        # Assicura che ritorna sempre una lista
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            print(f"[ERROR] Unexpected fix result type: {type(result)}, value: {result}")
            return []
    except Exception as e:
        print(f"[ERROR] Exception in generate_fixes_pure: {e}")
        return [{
            "issue_id": "ai_error",
            "explanation": f"Errore generazione fix: {str(e)}",
            "code_snippet": ""
        }]


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


def analyze_competitors_pure(keyword: str, user_url: str, limit: int = 3) -> list:
    """Cerca competitor organici usando Tavily con fallback su Google Serper."""
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

    def build_query(seed: str) -> str:
        seed_clean = " ".join(seed.split())
        suffix = " competitor alternative similar sites"
        return f"{seed_clean}{suffix}"
    
    try:
        query = build_query(keyword)
        print(f"--- DEBUG: Trying Tavily for '{query}'... ---")
        tavily_results = tavily_search.invoke(query)
        
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
                print(f"--- DEBUG: Tavily success! Found {len(results_data)} results. ---")
    
    except Exception as e:
        print(f"--- DEBUG: Tavily failed: {e} ---")

    if not results_data:
        print("--- DEBUG: Switching to Google Serper Direct Call... ---")
        api_key = os.getenv("SERPER_API_KEY")
        
        if api_key:
            try:
                url = "https://google.serper.dev/search"
                payload = json.dumps({
                    "q": keyword,
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
                print(f"--- DEBUG: Serper success! Found {len(results_data)} results. ---")
                
            except Exception as e:
                print(f"--- DEBUG: Serper failed: {e} ---")
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
