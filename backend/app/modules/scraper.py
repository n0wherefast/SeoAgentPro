import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_url(url: str):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except:
        return {"error": "Impossibile raggiungere il sito."}

    html = response.text
    soup = BeautifulSoup(html, "lxml")

    # TITLE
    title = soup.title.string if soup.title else None

    # META DESCRIPTION
    meta_description = None
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_description = meta_tag.get("content")

    # HEADINGS
    headings = {f"h{i}": [] for i in range(1, 7)}
    for i in range(1, 7):
        for h in soup.find_all(f"h{i}"):
            headings[f"h{i}"].append(h.get_text(strip=True))

    # IMMAGINI + ALT
    images = []
    for img in soup.find_all("img"):
        images.append({
            "src": urljoin(url, img.get("src", "")),
            "alt": img.get("alt"),
        })

    # PARAGRAFI
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]

    # LINKS (interni ed esterni)
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if href and not href.startswith("#") and not href.startswith("javascript:"):
            links.append({
                "href": urljoin(url, href),
                "text": a.get_text(strip=True)[:100],
                "is_external": not urljoin(url, href).startswith(url.split("/")[0] + "//" + url.split("/")[2])
            })

    # CANONICAL
    canonical = None
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        canonical = canonical_tag.get("href")

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

    # OPEN GRAPH
    open_graph = {}
    for og_tag in soup.find_all("meta"):
        prop = og_tag.get("property")
        if prop and prop.startswith("og:"):
            open_graph[prop] = og_tag.get("content")

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

    # Structured data (JSON-LD) presence
    structured_data_present = False
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if s.string and s.string.strip():
            structured_data_present = True
            break

    # COMPRESSIONE (dai response headers)
    compression = False
    if hasattr(response, 'headers'):
        encoding = response.headers.get("Content-Encoding", "").lower()
        if "gzip" in encoding or "br" in encoding or "deflate" in encoding:
            compression = True

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "images": images,
        "paragraphs": paragraphs,
        "links": links,
        "canonical": canonical,
        "favicon": favicon_url,
        "meta_viewport": meta_viewport,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "html_lang": html_lang,
        "structured_data_present": structured_data_present,
        "compression": compression,
        "status": "ok"
    }
