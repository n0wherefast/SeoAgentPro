"""
SEO Knowledge Base Indexer
Indexes SEO knowledge items into ChromaDB for RAG retrieval.
Runs once at startup (idempotent — skips if already indexed).
"""

import logging
import hashlib
from typing import List, Dict

from app.core.vector_store import get_collection, get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "seo_knowledge"

# ── SEO Knowledge Base (mirrored from frontend seoKnowledge.ts) ──
SEO_KNOWLEDGE_ITEMS: List[Dict[str, str]] = [
    # FUNDAMENTALS
    {
        "title": "SEO (Search Engine Optimization)",
        "category": "fundamentals",
        "content": "Insieme di tecniche per aumentare visibilità e traffico organico dai motori di ricerca. La SEO comprende tre pilastri principali: Technical SEO (struttura e performance del sito), On-Page SEO (contenuti e ottimizzazione delle pagine) e Off-Page SEO (backlink e autorità esterna). Una strategia SEO efficace integra tutti e tre per massimizzare il posizionamento organico."
    },
    {
        "title": "SERP (Search Engine Results Page)",
        "category": "fundamentals",
        "content": "La pagina dei risultati restituiti da un motore di ricerca per una query. Le SERP moderne includono risultati organici, annunci a pagamento (PPC), featured snippet, knowledge panel, People Also Ask, local pack e image carousel. Comprendere la composizione della SERP per le proprie keyword è fondamentale per scegliere la strategia di ottimizzazione corretta."
    },
    {
        "title": "Keyword Research",
        "category": "fundamentals",
        "content": "Processo di identificazione delle parole chiave che gli utenti cercano nel tuo settore. La keyword research analizza volume di ricerca, difficulty, intent (informazionale, navigazionale, transazionale, commerciale) e competitività. Strumenti come Ahrefs, SEMrush e Google Keyword Planner aiutano a trovare keyword a coda lunga (long-tail) con alto potenziale di conversione e bassa competizione."
    },
    {
        "title": "Backlink & Link Building",
        "category": "fundamentals",
        "content": "Link provenienti da altri siti che aumentano l'autorevolezza del tuo dominio. I backlink sono uno dei fattori di ranking più importanti. La qualità conta più della quantità: un link da un sito autorevole e pertinente vale più di centinaia di link da siti di bassa qualità. Strategie efficaci: guest posting, digital PR, broken link building, content linkabile."
    },
    {
        "title": "Crawling & Indexing",
        "category": "fundamentals",
        "content": "Come i motori di ricerca scoprono e catalogano le pagine del tuo sito. I crawler (Googlebot, Bingbot) seguono i link per scoprire pagine nuove. Dopo il crawling, il contenuto viene analizzato e inserito nell'indice. Problemi comuni: pagine orfane non linkate, crawl budget sprecato su URL irrilevanti, contenuti duplicati. Usa Google Search Console per monitorare lo stato di indicizzazione."
    },
    # TECHNICAL
    {
        "title": "Robots.txt",
        "category": "technical",
        "content": "File che comunica ai crawler quali sezioni del sito possono essere scansionate. Posizionato nella root del dominio (/robots.txt), utilizza direttive User-agent, Disallow, Allow e Sitemap. Errori comuni: bloccare accidentalmente risorse CSS/JS necessarie per il rendering, o bloccare intere sezioni con contenuto indicizzabile. Non è un meccanismo di sicurezza — le direttive sono advisory, non enforcement."
    },
    {
        "title": "Sitemap XML",
        "category": "technical",
        "content": "File che elenca le pagine del sito per aiutare i motori di ricerca a indicizzarle. La sitemap XML include URL, data di ultima modifica (lastmod), frequenza di cambio (changefreq) e priorità. Per siti grandi, si usano sitemap index che raggruppano più sitemap (max 50.000 URL o 50MB per file). Sitemap dinamiche generate dal CMS sono preferibili a quelle statiche."
    },
    {
        "title": "Canonical Tag",
        "category": "technical",
        "content": "Tag che indica l'URL preferito di una pagina per evitare contenuto duplicato. Il tag <link rel='canonical' href='...'> va nell'<head> di ogni pagina. Risolve problemi di URL con parametri, varianti HTTP/HTTPS, www/non-www, e paginazione. Self-referencing canonical (che punta a se stesso) è una best practice."
    },
    {
        "title": "Structured Data (Schema.org)",
        "category": "technical",
        "content": "Dati strutturati JSON-LD che aiutano i motori di ricerca a comprendere il contenuto. Lo schema markup abilita i rich snippet in SERP: stelle delle recensioni, prezzi, FAQ, breadcrumb, ricette, eventi. Il formato JSON-LD è preferito da Google rispetto a microdata o RDFa. Tipi comuni: Article, Product, FAQPage, Organization, BreadcrumbList, LocalBusiness."
    },
    {
        "title": "Hreflang Tag",
        "category": "technical",
        "content": "Attributo che indica la lingua e il target geografico di una pagina. Essenziale per siti multilingua/multiregione. Implementabile via HTML <link>, HTTP header o sitemap. Ogni pagina deve avere un hreflang self-referencing e reciproco. Il valore x-default indica la versione fallback."
    },
    {
        "title": "Redirect 301 vs 302",
        "category": "technical",
        "content": "Redirect permanenti e temporanei e il loro impatto sul SEO. 301 (permanente) trasferisce ~90-99% del link equity alla nuova URL. 302 (temporaneo) non trasferisce link equity. Usa 301 per migrazioni, cambio dominio, consolidamento URL. Evita catene di redirect (A→B→C) e loop. I redirect lato server (.htaccess, nginx) sono preferibili a quelli JavaScript."
    },
    # CONTENT & ON-PAGE
    {
        "title": "Meta Title & Description",
        "category": "content",
        "content": "Tag HTML fondamentali che descrivono la pagina in SERP. Il title tag (50-60 caratteri) è il fattore on-page più importante: deve includere la keyword target, essere unico per ogni pagina e invogliare il click. La meta description (150-160 caratteri) non è un fattore di ranking diretto ma influenza il CTR. Google può riscrivere la description se la ritiene non pertinente."
    },
    {
        "title": "Heading Structure (H1-H6)",
        "category": "content",
        "content": "Struttura gerarchica dei titoli per semantica e indicizzazione. L'H1 dovrebbe essere unico per pagina e contenere la keyword principale. Gli H2 suddividono i temi principali, H3 i sottotemi. Una struttura logica aiuta sia gli utenti (scansionabilità) sia i crawler (comprensione tematica). Non saltare livelli."
    },
    {
        "title": "Image Optimization & ALT Text",
        "category": "content",
        "content": "Ottimizzazione delle immagini per performance e accessibilità SEO. L'attributo alt descrive l'immagine per screen reader e crawler. Usa formati moderni (WebP, AVIF) per ridurre il peso. Il lazy loading (loading='lazy') migliora la performance. Dimensioni esplicite (width/height) prevengono il CLS."
    },
    {
        "title": "Internal Linking",
        "category": "content",
        "content": "Strategia di collegamenti tra le pagine del tuo sito per distribuire autorità. I link interni distribuiscono PageRank, stabiliscono la gerarchia del sito e aiutano il crawling. Usa anchor text descrittivi (non 'clicca qui'). Le pagine pillar dovrebbero ricevere più link interni. La regola dei 3 click: ogni pagina dovrebbe essere raggiungibile in max 3 click dalla homepage."
    },
    {
        "title": "E-E-A-T (Experience, Expertise, Authoritativeness, Trust)",
        "category": "content",
        "content": "Framework di Google per valutare la qualità e affidabilità dei contenuti. Introdotto nelle Quality Rater Guidelines, E-E-A-T è particolarmente importante per contenuti YMYL (Your Money, Your Life: salute, finanza, legale). Dimostra esperienza diretta, mostra le credenziali degli autori, ottieni citazioni da fonti autorevoli. Non è un fattore di ranking diretto ma influenza la valutazione complessiva."
    },
    {
        "title": "Open Graph & Twitter Cards",
        "category": "content",
        "content": "Meta tag che controllano l'aspetto dei link condivisi sui social network. I tag Open Graph (og:title, og:description, og:image, og:type) ottimizzano la preview su Facebook, LinkedIn e altri social. Le Twitter Cards fanno lo stesso per Twitter/X. Un'immagine OG di 1200x630px è il formato consigliato."
    },
    # PERFORMANCE
    {
        "title": "Core Web Vitals",
        "category": "performance",
        "content": "Metriche chiave di esperienza utente usate come fattore di ranking da Google. Le tre metriche principali: LCP (Largest Contentful Paint, target < 2.5s), INP (Interaction to Next Paint, target < 200ms), CLS (Cumulative Layout Shift, target < 0.1). Misurabili con Lighthouse, PageSpeed Insights, Chrome UX Report. Dal 2021 sono un fattore di ranking confermato."
    },
    {
        "title": "LCP (Largest Contentful Paint)",
        "category": "performance",
        "content": "Tempo di rendering dell'elemento più grande visibile nella viewport. Misura la velocità percepita di caricamento. Target: < 2.5 secondi. Ottimizzazioni: preload delle risorse critiche, CDN per immagini, formati moderni (WebP/AVIF), server-side rendering, riduzione del TTFB, eliminazione di render-blocking resources."
    },
    {
        "title": "CLS (Cumulative Layout Shift)",
        "category": "performance",
        "content": "Misura della stabilità visiva durante il caricamento. Target: < 0.1. Cause comuni: immagini senza dimensioni esplicite, ad/embed che si caricano in ritardo, font web che causano FOIT/FOUT. Fix: specifica sempre width/height per media, usa font-display: swap, riserva spazio per elementi dinamici."
    },
    {
        "title": "TTFB (Time To First Byte)",
        "category": "performance",
        "content": "Tempo impiegato dal server per rispondere alla richiesta iniziale. Target: < 800ms. Un TTFB alto indica problemi di server, database lento, o mancanza di caching. Ottimizzazioni: CDN (Cloudflare, Fastly), server caching (Redis, Varnish), database query optimization, HTTP/2 o HTTP/3."
    },
    {
        "title": "Compressione (Gzip / Brotli)",
        "category": "performance",
        "content": "Riduce il peso delle risorse trasferite dal server. Brotli offre ~15-20% di compressione in più rispetto a Gzip, ed è supportato da tutti i browser moderni. Comprimi HTML, CSS, JS, SVG e JSON. Non comprimere immagini (già compresse), font WOFF2 (già compressi internamente)."
    },
    # SECURITY
    {
        "title": "HTTPS / SSL-TLS",
        "category": "security",
        "content": "Crittografia del sito. Requisito obbligatorio per SEO e sicurezza. HTTPS è un fattore di ranking confermato da Google dal 2014. Tutti i siti dovrebbero usare HTTPS con certificato valido (Let's Encrypt è gratuito). Verifica: nessun mixed content, redirect 301 da HTTP a HTTPS, HSTS header attivo."
    },
    {
        "title": "Security Headers",
        "category": "security",
        "content": "Intestazioni HTTP che migliorano la sicurezza del sito. Header essenziali: Content-Security-Policy (previene XSS), Strict-Transport-Security (forza HTTPS), X-Content-Type-Options: nosniff, X-Frame-Options (previene clickjacking), Referrer-Policy, Permissions-Policy. Testa i tuoi header su securityheaders.com."
    },
    {
        "title": "Mixed Content",
        "category": "security",
        "content": "Risorse HTTP caricate su pagine HTTPS che compromettono la sicurezza. Il mixed content si verifica quando una pagina HTTPS carica risorse via HTTP. I browser bloccano il mixed content attivo (script, iframe). Fix: aggiorna tutti gli URL a HTTPS, usa protocol-relative URL o URL relativi."
    },
    # ADVANCED
    {
        "title": "Competitor Analysis",
        "category": "advanced",
        "content": "Analisi dei concorrenti per individuare gap di contenuto e strategie vincenti. Include: keyword gap, content gap, backlink gap, analisi SERP feature ownership, confronto di autorità di dominio. Usa i dati per definire priorità: colmare i gap più redditizi prima."
    },
    {
        "title": "Topic Clustering & Pillar Pages",
        "category": "advanced",
        "content": "Strategia di organizzazione dei contenuti per massimizzare l'autorità tematica. Una pillar page copre un argomento ampio e linka a cluster di pagine specifiche. Ogni cluster page linka indietro alla pillar. Questo modello aiuta Google a capire la relazione tra contenuti e aumenta l'autorità topica complessiva."
    },
    {
        "title": "SEO per JavaScript (SPA/CSR)",
        "category": "advanced",
        "content": "Sfide e soluzioni SEO per siti basati su framework JavaScript. Google esegue JavaScript ma con ritardo. Problemi: contenuto non renderizzato, link dinamici non crawlabili, meta tag iniettati lato client. Soluzioni: Server-Side Rendering (SSR), Static Site Generation (SSG), Incremental Static Regeneration (ISR)."
    },
    {
        "title": "SEO Internazionale",
        "category": "advanced",
        "content": "Strategie per posizionare un sito in più paesi e lingue. Strutture URL: ccTLD (example.it), subdomain (it.example.com), subfolder (example.com/it/). Implementa hreflang correttamente, usa Google Search Console per il targeting geografico, crea contenuti localizzati (non solo tradotti)."
    },
    {
        "title": "Log File Analysis",
        "category": "advanced",
        "content": "Analisi dei log del server per capire come Googlebot interagisce con il sito. I log del server mostrano esattamente quali URL Googlebot crawla, con quale frequenza e quali status code riceve. Permette di identificare: crawl budget sprecato su pagine inutili, pagine importanti mai crawlate, errori 5xx."
    },
    # TOOLS
    {
        "title": "PageSpeed Insights / Lighthouse",
        "category": "tools",
        "content": "Strumenti per misurare performance e suggerire ottimizzazioni. Lighthouse misura Performance, Accessibility, Best Practices, SEO e PWA. PageSpeed Insights combina dati di laboratorio con dati reali (CrUX). Lo score 0-100 è calcolato pesando le metriche: LCP (25%), TBT (30%), CLS (25%), FCP (10%), Speed Index (10%)."
    },
    {
        "title": "Google Search Console",
        "category": "tools",
        "content": "Strumento gratuito di Google per monitorare la presenza del sito nei risultati di ricerca. Funzionalità chiave: report sulle performance (click, impressioni, CTR, posizione media per query), copertura dell'indice, ispezione URL, sitemap submission, Core Web Vitals report, link report."
    },
    {
        "title": "SEO Scoring & Audit",
        "category": "tools",
        "content": "Valutazione automatizzata della qualità SEO di una pagina. Un audit SEO sistematico verifica: meta tag, struttura heading, immagini (alt, dimensioni, formato), link (interni, esterni, broken), performance (Core Web Vitals), sicurezza (HTTPS, headers), structured data, mobile-friendliness."
    },
    {
        "title": "AI Autofix & Code Generation",
        "category": "tools",
        "content": "Suggerimenti e fix generati da AI per correggere problemi SEO. I modelli LLM (GPT-4, Claude) possono generare snippet di codice specifici per lo stack tecnologico del sito. SEO Agent Pro rileva automaticamente lo stack e genera codice compatibile con meta tag HTML, schema JSON-LD, configurazioni, componenti React."
    },
]


def _doc_id(title: str) -> str:
    """Generate a deterministic document ID from title."""
    return hashlib.md5(title.encode()).hexdigest()


def index_knowledge_base(force: bool = False) -> int:
    """
    Index all SEO knowledge items into ChromaDB.
    Idempotent: skips if collection already has the expected number of docs.
    
    Args:
        force: If True, re-indexes even if count matches.
        
    Returns:
        Number of documents indexed.
    """
    collection = get_collection(COLLECTION_NAME)
    existing_count = collection.count()
    expected_count = len(SEO_KNOWLEDGE_ITEMS)
    
    if not force and existing_count >= expected_count:
        logger.info(
            "Knowledge base already indexed (%d docs). Skipping.",
            existing_count,
        )
        return existing_count
    
    logger.info("Indexing %d SEO knowledge items into ChromaDB...", expected_count)
    
    embeddings = get_embeddings()
    
    # Prepare documents
    ids = []
    documents = []
    metadatas = []
    
    for item in SEO_KNOWLEDGE_ITEMS:
        doc_text = f"{item['title']}\n\n{item['content']}"
        ids.append(_doc_id(item["title"]))
        documents.append(doc_text)
        metadatas.append({
            "title": item["title"],
            "category": item["category"],
            "source": "seo_knowledge_base",
        })
    
    # Embed all documents
    vectors = embeddings.embed_documents(documents)
    
    # Upsert into ChromaDB
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=vectors,
    )
    
    final_count = collection.count()
    logger.info("✅ Knowledge base indexed: %d documents", final_count)
    return final_count


def query_knowledge(query: str, n_results: int = 5, category: str | None = None) -> list[dict]:
    """
    Query the SEO knowledge base for relevant documents.
    
    Args:
        query: The search query (will be embedded).
        n_results: Number of results to return.
        category: Optional category filter.
        
    Returns:
        List of dicts with 'content', 'title', 'category', 'distance'.
    """
    collection = get_collection(COLLECTION_NAME)
    
    if collection.count() == 0:
        logger.warning("Knowledge base is empty. Run index_knowledge_base() first.")
        return []
    
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    
    where_filter = {"category": category} if category else None
    
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
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "distance": dist,
            })
    
    return output
