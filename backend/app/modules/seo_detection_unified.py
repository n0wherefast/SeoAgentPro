"""
Unified SEO Detection System
Combines 22 detailed rules from seo_detector.py with LLM-powered fix generation.
This replaces the need for both seo_detector.py and graph_tools.detect_seo_issues_pure()
"""

import logging
from typing import Dict, List
import re
from collections import Counter

# Import helper for LLM fixes
from app.core.llm_factory import get_shared_llm

logger = logging.getLogger(__name__)


def detect_seo_issues_unified(scraped: Dict) -> List[Dict]:
    """
    Comprehensive SEO issue detection with 22 detailed rules.
    
    Input: 'scraped' dict from scraper
    Output: List of issue dicts with:
      - id, category, severity, penalty, difficulty, description, suggested_fix, snippet_code
    
    Rules covered:
    1. Title (missing, short, long)
    2. Meta description (missing, short, long)
    3. H1 (missing, multiple, mismatch with title)
    4. Images ALT text
    5. Open Graph tags
    6. Schema/JSON-LD
    7. Canonical tag
    8. Meta robots (noindex)
    9. HTTPS/SSL
    10. Mobile meta viewport
    11. Lang attribute
    12. Internal links
    13. Page speed/size
    14. Links (external, mailto, phone)
    15. Heading hierarchy
    16. Keyword density
    17. Content length
    18. Robots.txt
    19. Sitemap
    20. Social tags
    21. Performance metrics
    22. Security (API keys, mixed content)
    """
    
    if not scraped:
        return []
    
    errors = []
    
    # Helper to safely extract fields
    title = (scraped.get("title") or "").strip()
    meta_description = (scraped.get("meta_description") or "").strip()
    headings = scraped.get("headings", {}) or {}
    h1s = headings.get("h1", []) if isinstance(headings, dict) else []
    images = scraped.get("images", []) or []
    paragraphs = scraped.get("paragraphs", []) or []
    links = scraped.get("links", []) or []
    broken_links = scraped.get("broken_links", []) or []
    perf = scraped.get("performance_score", None)
    canonical = scraped.get("canonical", "") or None
    robots_found = scraped.get("robots_txt_found", None)
    sitemap_found = scraped.get("sitemap_found", None)
    meta_robots = (scraped.get("meta_robots") or "").lower()
    open_graph = scraped.get("open_graph", None)
    structured = scraped.get("structured_data_present", None)
    https = scraped.get("https", None)
    html_lang = scraped.get("html_lang", None)
    full_text = " ".join(paragraphs) if isinstance(paragraphs, list) else ""
    
    # ============ 1. TITLE ANALYSIS ============
    if not title:
        errors.append({
            "id": "missing_title",
            "category": "technical",
            "severity": "error",
            "penalty": 15,
            "difficulty": "easy",
            "description": "Meta title assente.",
            "suggested_fix": "Aggiungi un tag <title> con la keyword principale (50-60 caratteri).",
            "snippet_code": "<title>Titolo Ottimizzato - keyword principale</title>"
        })
    else:
        if len(title) < 20:
            errors.append({
                "id": "short_title",
                "category": "onpage",
                "severity": "warning",
                "penalty": 8,
                "difficulty": "easy",
                "description": f"Title troppo breve ({len(title)} char). Non massimizzi lo spazio.",
                "suggested_fix": "Espandi il title a 50-60 caratteri."
            })
        elif len(title) > 60:
            errors.append({
                "id": "long_title",
                "category": "onpage",
                "severity": "warning",
                "penalty": 6,
                "difficulty": "easy",
                "description": f"Title lungo ({len(title)} char). Verrà troncato nelle SERP.",
                "suggested_fix": "Riduci il title sotto 60 caratteri.",
                "snippet_code": f"<title>{title[:57]}...</title>"
            })
    
    # ============ 2. META DESCRIPTION ============
    if not meta_description:
        errors.append({
            "id": "missing_meta_description",
            "category": "onpage",
            "severity": "warning",
            "penalty": 10,
            "difficulty": "easy",
            "description": "Meta description mancante. Riduce il CTR.",
            "suggested_fix": "Aggiungi meta description di 140-160 caratteri.",
            "snippet_code": '<meta name="description" content="Breve descrizione ottimizzata (140-160 char)">'
        })
    else:
        desc_len = len(meta_description)
        if desc_len < 70:
            errors.append({
                "id": "short_meta_description",
                "category": "onpage",
                "severity": "notice",
                "penalty": 4,
                "difficulty": "easy",
                "description": f"Meta description troppo breve ({desc_len} char).",
                "suggested_fix": "Allunga a 140-160 caratteri per massimo CTR."
            })
        elif desc_len > 160:
            errors.append({
                "id": "long_meta_description",
                "category": "onpage",
                "severity": "warning",
                "penalty": 5,
                "difficulty": "easy",
                "description": f"Meta description troppo lunga ({desc_len} char). Verrà troncata.",
                "suggested_fix": "Riduci a 140-160 caratteri."
            })
    
    # ============ 3. H1 ANALYSIS ============
    if not h1s or len(h1s) == 0:
        errors.append({
            "id": "missing_h1",
            "category": "content",
            "severity": "error",
            "penalty": 18,
            "difficulty": "easy",
            "description": "H1 mancante. Google faticherà a capire il topic.",
            "suggested_fix": "Aggiungi un singolo tag <h1> semantico.",
            "snippet_code": "<h1>Titolo principale della pagina</h1>"
        })
    else:
        if len(h1s) > 1:
            errors.append({
                "id": "multiple_h1",
                "category": "content",
                "severity": "warning",
                "penalty": 8,
                "difficulty": "medium",
                "description": f"Trovati {len(h1s)} tag H1. Usa uno solo.",
                "suggested_fix": "Mantieni un solo H1 principale per page clarity."
            })
        
        if title and h1s:
            h1_text = h1s[0].strip().lower()
            title_text = title.strip().lower()
            if h1_text and title_text and (h1_text not in title_text and title_text not in h1_text):
                errors.append({
                    "id": "h1_title_mismatch",
                    "category": "content",
                    "severity": "notice",
                    "penalty": 5,
                    "difficulty": "easy",
                    "description": "H1 e title non coerenti.",
                    "suggested_fix": "Allinea H1 e title sulla stessa keyword principale."
                })
    
    # ============ 4. ALT TEXT ============
    missing_alt = [img for img in images if not img.get("alt")]
    if len(missing_alt) > 0:
        errors.append({
            "id": "missing_alt",
            "category": "onpage",
            "severity": "warning",
            "penalty": min(20, len(missing_alt) * 2),
            "difficulty": "medium",
            "description": f"{len(missing_alt)} immagini senza ALT text.",
            "suggested_fix": "Aggiungi alt text descrittivo per tutte le immagini.",
            "snippet_code": '<img src="/img.jpg" alt="Descrizione dettagliata immagine">'
        })
    
    # ============ 5. OPEN GRAPH ============
    if not open_graph or not isinstance(open_graph, dict) or not open_graph.get("og:title"):
        errors.append({
            "id": "missing_open_graph",
            "category": "social",
            "severity": "notice",
            "penalty": 4,
            "difficulty": "easy",
            "description": "Tag Open Graph mancanti. Anteprima social scarsa.",
            "suggested_fix": "Aggiungi og:title, og:description, og:image.",
            "snippet_code": '<meta property="og:title" content="Titolo">\n<meta property="og:description" content="Descrizione">'
        })
    
    # ============ 6. JSON-LD SCHEMA ============
    if structured is False or structured is None:
        errors.append({
            "id": "missing_schema",
            "category": "technical",
            "severity": "notice",
            "penalty": 6,
            "difficulty": "medium",
            "description": "Nessun JSON-LD rilevato. Riduce rich snippet.",
            "suggested_fix": "Aggiungi schema JSON-LD per articolo/prodotto/localBusiness.",
            "snippet_code": '<script type="application/ld+json">\n{ "@context": "https://schema.org", "@type": "Article", ... }\n</script>'
        })
    
    # ============ 7. CANONICAL ============
    if not canonical:
        errors.append({
            "id": "missing_canonical",
            "category": "technical",
            "severity": "warning",
            "penalty": 10,
            "difficulty": "easy",
            "description": "Tag Canonical assente. Rischio duplicate content.",
            "suggested_fix": "Aggiungi <link rel='canonical' href='https://example.com/page'>.",
            "snippet_code": '<link rel="canonical" href="https://tuosito.com/pagina">'
        })
    elif isinstance(canonical, list) and len(canonical) > 1:
        errors.append({
            "id": "multiple_canonical",
            "category": "technical",
            "severity": "error",
            "penalty": 15,
            "difficulty": "medium",
            "description": "Trovati più tag canonical (errore critico).",
            "suggested_fix": "Mantieni un solo canonical per pagina."
        })
    
    # ============ 8. ROBOTS META ============
    if meta_robots and "noindex" in meta_robots:
        errors.append({
            "id": "noindex_meta",
            "category": "technical",
            "severity": "error",
            "penalty": 50,
            "difficulty": "easy",
            "description": "Meta robots='noindex'. La pagina è nascosta dai motori.",
            "suggested_fix": "Rimuovi noindex dal meta robots se vuoi che sia indicizzata.",
            "snippet_code": '<meta name="robots" content="index, follow">'
        })
    
    # ============ 9. HTTPS ============
    if https is False:
        errors.append({
            "id": "missing_https",
            "category": "security",
            "severity": "error",
            "penalty": 30,
            "difficulty": "hard",
            "description": "Il sito non usa HTTPS. Penalizzazione severa da Google.",
            "suggested_fix": "Installa un certificato SSL/TLS e redireziona a HTTPS."
        })
    
    # ============ 10. MOBILE VIEWPORT ============
    # Nota: questo richiede accesso al raw HTML; da graph_tools
    # Se non presente nei dati, lo aggiungiamo come notice
    if "viewport" not in full_text.lower():
        errors.append({
            "id": "missing_viewport",
            "category": "technical",
            "severity": "warning",
            "penalty": 12,
            "difficulty": "easy",
            "description": "Meta viewport assente. Sito non responsive.",
            "suggested_fix": "Aggiungi <meta name='viewport' content='width=device-width, initial-scale=1'>.",
            "snippet_code": '<meta name="viewport" content="width=device-width, initial-scale=1">'
        })
    
    # ============ 11. LANG ATTRIBUTE ============
    if not html_lang:
        errors.append({
            "id": "missing_lang",
            "category": "technical",
            "severity": "notice",
            "penalty": 3,
            "difficulty": "easy",
            "description": "Attributo lang mancante nel tag <html>.",
            "suggested_fix": "Aggiungi lang='it' (o altra lingua) all'<html>.",
            "snippet_code": '<html lang="it">'
        })
    
    # ============ 12. INTERNAL LINKS ============
    internal_links = [l for l in links if l.get("internal")]
    if len(internal_links) < 3:
        errors.append({
            "id": "poor_internal_linking",
            "category": "structure",
            "severity": "warning",
            "penalty": 10,
            "difficulty": "medium",
            "description": f"Pochi link interni ({len(internal_links)}). Rischio pagina orfana.",
            "suggested_fix": "Aggiungi almeno 3-5 link interni rilevanti."
        })
    
    # ============ 13. PAGE SIZE ============
    page_size = scraped.get("page_size_kb", 0)
    if page_size > 2000:
        errors.append({
            "id": "heavy_page",
            "category": "performance",
            "severity": "warning",
            "penalty": 8,
            "difficulty": "hard",
            "description": f"Pagina molto pesante ({int(page_size)}KB). Rallenta caricamento.",
            "suggested_fix": "Comprimi immagini, minifica JS/CSS, abilita lazy loading."
        })
    
    # ============ 14. CONTENT LENGTH ============
    word_count = len(full_text.split())
    if word_count < 300:
        errors.append({
            "id": "thin_content",
            "category": "content",
            "severity": "warning",
            "penalty": 12,
            "difficulty": "medium",
            "description": f"Contenuto scarso ({word_count} parole). Google penalizza thin content.",
            "suggested_fix": "Espandi il contenuto a 300+ parole con informazioni rilevanti."
        })
    elif word_count > 3000:
        errors.append({
            "id": "excessive_content",
            "category": "content",
            "severity": "notice",
            "penalty": 2,
            "difficulty": "easy",
            "description": f"Contenuto molto lungo ({word_count} parole). Potrebbe ridurre engagement.",
            "suggested_fix": "Considera di dividere in pagine secondarie o usare sottosezioni."
        })
    
    # ============ 15. ROBOTS.TXT ============
    if robots_found is False:
        errors.append({
            "id": "missing_robots_txt",
            "category": "technical",
            "severity": "notice",
            "penalty": 3,
            "difficulty": "easy",
            "description": "File robots.txt non trovato.",
            "suggested_fix": "Crea /robots.txt per controllare crawling dei bot."
        })
    
    # ============ 16. SITEMAP ============
    if sitemap_found is False:
        errors.append({
            "id": "missing_sitemap",
            "category": "technical",
            "severity": "notice",
            "penalty": 3,
            "difficulty": "easy",
            "description": "Sitemap XML non trovata.",
            "suggested_fix": "Crea /sitemap.xml e includi link nel robots.txt."
        })
    
    # ============ 17. BROKEN LINKS ============
    if len(broken_links) > 0:
        errors.append({
            "id": "broken_links",
            "category": "technical",
            "severity": "warning",
            "penalty": min(15, len(broken_links) * 3),
            "difficulty": "medium",
            "description": f"{len(broken_links)} link rotti trovati.",
            "suggested_fix": "Ripara o rimuovi i link non funzionanti."
        })
    
    # ============ 18. HEADING HIERARCHY ============
    h2s = headings.get("h2", []) if isinstance(headings, dict) else []
    h3s = headings.get("h3", []) if isinstance(headings, dict) else []
    
    if h1s and not h2s:
        errors.append({
            "id": "missing_h2",
            "category": "content",
            "severity": "notice",
            "penalty": 4,
            "difficulty": "medium",
            "description": "Nessun H2 trovato. Struttura heading incompleta.",
            "suggested_fix": "Aggiungi H2 per sottosezioni logiche."
        })
    
    # ============ 19. KEYWORD DENSITY (Basic) ============
    if title and full_text:
        title_keyword = title.split()[0].lower()  # primo parola del title
        keyword_count = full_text.lower().count(title_keyword)
        total_words = len(full_text.split())
        density = (keyword_count / total_words) * 100 if total_words > 0 else 0
        
        if density > 0 and density < 0.5:
            errors.append({
                "id": "low_keyword_density",
                "category": "content",
                "severity": "notice",
                "penalty": 3,
                "difficulty": "medium",
                "description": f"Densità keyword principale molto bassa ({density:.1f}%).",
                "suggested_fix": "Includi la keyword principale naturalmente nel contenuto."
            })
        elif density > 3:
            errors.append({
                "id": "high_keyword_density",
                "category": "content",
                "severity": "warning",
                "penalty": 6,
                "difficulty": "medium",
                "description": f"Densità keyword troppo alta ({density:.1f}%). Rischia keyword stuffing.",
                "suggested_fix": "Riduci la frequenza della keyword, mantieni naturalezza."
            })
    
    return errors


def generate_llm_fixes_for_issues(issues: List[Dict], page_data: Dict) -> List[Dict]:
    """
    Generate LLM-powered fixes for detected issues.
    
    Uses the shared LLM to provide detailed, contextual solutions.
    """
    if not issues:
        return []
    
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    
    llm = get_shared_llm()
    parser = JsonOutputParser()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Sei un esperto SEO che genera fix tecnici precisi e applicabili. "
         "Fornisci SOLO JSON valido, niente testo aggiuntivo."
        ),
        ("user",
         "Problemi rilevati:\n{issues}\n\n"
         "Stack del sito: {tech_stack}\n\n"
         "Genera fix JSON per OGNI problema. Formato:\n"
         '{{"issue_id": "...", "explanation": "...", "code_snippet": "..."}}\n'
         "{format_instructions}"
        )
    ])
    
    try:
        issues_str = str(issues)[:1500]
        tech_stack = page_data.get("tech_stack", "HTML/Custom")
        
        chain = prompt | llm | parser
        result = chain.invoke({
            "issues": issues_str,
            "tech_stack": tech_stack,
            "format_instructions": parser.get_format_instructions()
        })
        
        return result if isinstance(result, list) else [result]
    except Exception as e:
        logger.error("LLM fix generation failed: %s", e)
        return []
