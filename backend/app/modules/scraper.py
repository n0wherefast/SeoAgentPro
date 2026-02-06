from app.modules.graph_tools import fetch_page_playwright
from app.modules.graph_tools import  extract_seo_elements_pure
# def smart_scrape_url(url: str):
#     """
#     Scraper unificato: usa requests+BS4, poi Playwright solo se mancano dati chiave (es. JSON-LD).
#     Restituisce dict con campo 'scraper_used'.
#     """
#     # Prima pass: scraping classico
#     data = scrape_url(url)
#     data["scraper_used"] = "requests"
#     # Se manca JSON-LD o altri dati critici, riprova con Playwright
#     if not data.get("structured_data_present"):
#         html = fetch_page_playwright(url)
#         if html and not html.startswith("ERROR"):
#             from bs4 import BeautifulSoup
#             soup = BeautifulSoup(html, "lxml")
#             # Ricalcola solo i dati dinamici chiave
#             structured_data_present = False
#             for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
#                 if s.string and s.string.strip():
#                     structured_data_present = True
#                     break
#             data["structured_data_present"] = structured_data_present
#             data["scraper_used"] = "playwright"
#             # (opzionale) puoi aggiornare altri campi dinamici qui
#     return data
def smart_scrape_url(url: str):
    """
    Scraper unificato: usa requests+BS4, poi Playwright solo se mancano dati chiave.
    """
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
            # Nota: Non passiamo 'response' qui perché Playwright non restituisce un oggetto response requests compatibile,
            # quindi 'compression' sarà False (corretto, perché non possiamo verificarlo facilmente qui).
            data = extract_seo_elements_pure(html, url, soup)
            data["html_content"] = html
            
            data["scraper_used"] = "playwright"
            
    return data


from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

def scrape_url(url: str):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except:
        return {"error": "Impossibile raggiungere il sito."}

    html = response.text
    soup = BeautifulSoup(html, "lxml")

    data = extract_seo_elements_pure(html, url, soup)
    data["html_content"] = html
    return data
