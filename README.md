<div align="center">

# 🚀 SEO-Agent

### AI-Powered SEO Audit Platform

**Analisi tecnica · Competitor Intelligence · Report AI · RAG Chat · Real-time Streaming**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-CC785C?style=for-the-badge&logo=anthropic&logoColor=white)](https://anthropic.com)
[![Mistral](https://img.shields.io/badge/Mistral-Devstral-5A67D8?style=for-the-badge)](https://mistral.ai)
[![Ollama](https://img.shields.io/badge/Ollama-Llama_3.3-000000?style=for-the-badge)](https://ollama.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-FF6F61?style=for-the-badge)](https://www.trychroma.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

<img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="version" />
<img src="https://img.shields.io/badge/status-active--development-brightgreen?style=flat-square" alt="status" />

</div>

---

## 📖 Panoramica

**SEO-PRO** è una piattaforma open-source full-stack per l'audit SEO professionale, potenziata dall'intelligenza artificiale. Combina scraping web avanzato, 22+ regole di analisi SEO, competitor intelligence e generazione di report AI in un'unica dashboard moderna e interattiva.

Supporta **4 provider LLM** intercambiabili a runtime: **OpenAI** (GPT-4o), **Anthropic** (Claude), **Mistral/Devstral** e **Ollama** (Llama 3.3, modelli locali). Basta selezionare il provider dal selettore nella dashboard.

Progettata per **agenzie SEO**, **freelancer**, **developer** e **marketer**, SEO-PRO trasforma ore di audit manuale in scansioni automatiche in tempo reale con fix tecnici pronti all'uso.

### ✨ Caratteristiche Principali

| Feature | Descrizione |
|---------|-------------|
| ⚡ **Quick Scan** | Analisi SEO rapida (~5s) con score, problemi on-page e metriche tecniche |
| 🔍 **Full Scan** | Scansione completa con competitor analysis, keyword tracking e 5 report AI |
| 🤖 **Advanced AI Audit** | Workflow orchestrato con scraping, competitor discovery, fix generation e report Markdown |
| 🧠 **Autonomous Mode** | Agente ReAct AI-driven con loop adattivo e circuit breaker |
| 📊 **Real-time Streaming** | SSE (Server-Sent Events) per risultati progressivi in tempo reale |
| 🏆 **Competitor Intelligence** | Ranking, radar chart, keyword gap/overlap e clustering automatico |
| 🛠️ **AI Fix Generation** | Fix tecnici con codice pronto, schema markup JSON-LD e content expansion |
| 📋 **Report Professionali** | Export PDF e Markdown con roadmap strategica personalizzata |
| 🧬 **RAG (Retrieval-Augmented Generation)** | Knowledge base SEO + storico scansioni indicizzati in ChromaDB per risposte contestuali |
| 💬 **AI Chat** | Chat interattiva con streaming, memoria conversazionale e contesto multi-livello |
| 🧠 **Multi-LLM** | Supporto OpenAI, Anthropic (Claude), Mistral (Devstral), Ollama (Llama) con switch a runtime |

---

## 🎯 Modalità di Scansione

```
┌──────────────────────────────────────────────┐
│                         SEO-PRO Scan Modes   │
├──────────────┬───────────────┬───────────────┤
│   ⚡ Quick    │   🔍 Full     │  🤖 Advanced 
│   ~5 sec     │   ~30 sec     │   ~60 sec     │  
├──────────────┼───────────────┼───────────────┼
│ ✅ Scraping  │ ✅ Scraping    │ ✅ Scraping │       
│ ✅ On-page   │ ✅ On-page     │ ✅ On-page  │           
│ ✅ Technical │ ✅ Technical   │ ✅ Technical │ 
│ ✅ Score     │ ✅ Performance │ ✅ Performance │ 
│              │ ✅ Authority   │ ✅ Competitors │ 
│              │ ✅ AI AutoFix  │ ✅ AI Fixes    │ 
│              │ ✅ AI Schema   │ ✅ AI Report   │ 
│              │ ✅ AI Roadmap  │ ✅ Sitemap     │ 
│              │ ✅ Keywords    │              │ 
└──────────────┴───────────────┴───────────────┴───
```

---

## 🧩 Architettura

```
SEO-PRO/
├── backend/                        # 🐍 FastAPI Backend
│   ├── app/
│   │   ├── main.py                 # Entry point + CORS + routers + startup indexing
│   │   ├── core/                   # Config, LLM Factory, Cache, RAG
│   │   │   ├── llm_factory.py      # Multi-provider LLM factory (OpenAI/Anthropic/Mistral/Ollama)
│   │   │   ├── vector_store.py     # ChromaDB singleton + OpenAI Embeddings
│   │   │   ├── knowledge_indexer.py# SEO Knowledge Base indexer + query (34 documenti)
│   │   │   ├── cache_manager.py    # LRU cache per risposte LLM
│   │   │   └── async_helpers.py    # Thread pool per keyword extraction
│   │   ├── modules/                # Business logic
│   │   │   ├── scraper.py          # Smart scraping (requests → HTTPX → Playwright)
│   │   │   ├── seo_detection_unified.py  # 22+ regole SEO con penalità pesate
│   │   │   ├── seo_rules.py        # Scoring engine con pesi per categoria
│   │   │   ├── seo_technical.py    # Check tecnici (robots, sitemap, HTTPS, headers)
│   │   │   ├── graph_agent.py      # Orchestrator workflow (4 modalità)
│   │   │   ├── graph_tools.py      # SEO extraction + competitor discovery
│   │   │   ├── ai_fix_agents.py    # Fix tecnici AI con RAG context augmentation
│   │   │   ├── scan_store.py       # Persiste scansioni in ChromaDB per RAG
│   │   │   ├── chat_agent.py       # AI Chat con RAG multi-collection + memory
│   │   │   ├── ai_schema_agent.py  # JSON-LD schema generation
│   │   │   ├── ai_content_expander.py  # AI content optimization
│   │   │   ├── ai_roadmap_agent.py # Roadmap strategica con priorità
│   │   │   ├── ai_strategy_agent.py# Strategia competitiva AI
│   │   │   ├── authority_engine.py # Authority scoring
│   │   │   ├── agents/             # AI Agents (BaseAgent ABC, ReAct, Authority, Keyword)
│   │   │   └── competitor/         # Competitor module (ranking, radar, keywords, clustering)
│   │   └── routes/                 # API endpoints
│   │       ├── scan.py             # Quick scan
│   │       ├── scan_full.py        # Full scan + scan_store integration
│   │       ├── graph_scan.py       # Advanced AI audit
│   │       └── chat.py             # AI Chat SSE endpoint
│   ├── chroma_data/                # ChromaDB persistent storage (auto-created)
│   └── requirements.txt
│
├── frontend/seo-dashboard/         # ⚛️ Next.js 16 Frontend
│   ├── app/
│   │   ├── layout.tsx              # Root layout con Sidebar + Header
│   │   ├── page.tsx                # Home dashboard
│   │   ├── quick-scan/             # Quick scan page (SSE streaming)
│   │   ├── full-scan/              # Full scan page (competitor + keywords)
│   │   ├── graph-scan/             # Advanced audit (tabs: Overview/Issues/Fixes/Report)
│   │   ├── knowledge-seo/          # SEO knowledge base / glossario
│   │   ├── chat/                   # AI Chat page (full-screen)
│   │   ├── components/             # Shared components
│   │   │   ├── ChatPanel.tsx       # Chat UI con streaming, markdown, suggestions
│   │   │   ├── LLMSelector.tsx     # Dropdown per switch LLM provider/model a runtime
│   │   │   ├── ai/                 # AI result renderers (Autofix, Roadmap, Schema, Content)
│   │   │   └── competitor/         # Competitor charts (Ranking, Radar, Keywords, Strategy)
│   │   └── types/                  # TypeScript type definitions
│   └── lib/api.ts                  # API client + SSE event handlers
│
└── README.md
```

### Flusso Dati (con RAG)

```
[Browser] → [Next.js Frontend] → SSE EventSource → [FastAPI Backend]
                                                         │
                    ┌──────────────────────────────────────┤
                    ▼                                      ▼
             [Smart Scraper]                       [AI Agents (Multi-LLM)]
             requests → HTTPX                      OpenAI / Anthropic /
             → Playwright                          Mistral / Ollama
                    │                          ┌───────────┤───────────┐
                    ▼                          ▼           ▼           ▼
             [SEO Detection]            [Fix Gen]    [Report Gen]  [Chat Agent]
             22+ rules engine           RAG-enhanced  [Roadmap]    RAG + Memory
                    │                    (multi-LLM)  [Strategy]   (multi-LLM)
                    ▼                          │           │           │
             [Scoring Engine]                  └─────┬─────┘     ┌────┘
             weighted by category                    │           │
                    │                          ┌─────▼───────────▼─────┐
                    │                          │   ChromaDB Vector DB   │
                    │                          │  ┌──────────────────┐  │
                    │                          │  │ seo_knowledge    │  │
                    │                          │  │ (34 documenti)   │  │
                    │                          │  ├──────────────────┤  │
                    │                          │  │ scan_results     │  │
                    │                          │  │ (storico scans)  │  │
                    │                          │  └──────────────────┘  │
                    │                          └───────────────────────┘
                    │                                      │
                    └──────────────┬───────────────────────┘
                                   ▼
                        [SSE Stream → Real-time UI]
```

---

## ⚡ Quick Start

### Prerequisiti

- **Python** 3.11+ 
- **Node.js** 18+
- **OpenAI API Key** ([ottieni qui](https://platform.openai.com/api-keys))
- **Playwright** (opzionale, per scraping JS-rendered pages)

### 1. Clona il Repository

```bash
git clone https://github.com/tuo-utente/seo-pro.git
cd seo-pro
```

### 2. Setup Backend

```bash
# Crea virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# Installa dipendenze
pip install -r backend/requirements.txt

# (Opzionale) Installa Playwright per scraping avanzato
pip install playwright
playwright install chromium

# Configura variabili d'ambiente
cp backend/.env.example backend/.env
# Modifica backend/.env con le tue API keys
```

### 3. Configura Environment Variables

Crea il file `backend/.env`:

```env
# ── LLM Provider (scegli uno) ──
LLM_PROVIDER=openai                  # openai | anthropic | mistral | ollama
LLM_MODEL=gpt-4o-mini                # oppure: claude-sonnet-4-20250514, devstral-small-2505, llama3.3

# ── API Keys (configura quelli che usi) ──
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# ── Ollama (modelli locali, nessuna API key necessaria) ──
OLLAMA_BASE_URL=http://localhost:

# Opzionale — per competitor discovery
TAVILY_API_KEY=tvly-your-key-here

# Opzionale — per PageSpeed Insights
PAGESPEED_API_KEY=your-key-here
```

### 4. Setup Frontend

```bash
cd frontend/seo-dashboard
npm install

# Configura API backend URL
echo "NEXT_PUBLIC_BACKEND_API=http://127.0.0.1:8000/api" > .env.local
```

### 5. Avvia i Server

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd frontend/seo-dashboard
npm run dev
```

### 6. Accedi alla Dashboard

Apri **[http://localhost:3000](http://localhost:3000)** nel browser.

---

## 🔌 API Endpoints

| Endpoint | Metodo | Tipo | Descrizione |
|----------|--------|------|-------------|
| `/api/health` | GET | JSON | Health check del server (include stato RAG e LLM provider attivo) |
| `/api/llm/config` | GET | JSON | Restituisce provider/modello attivo e opzioni disponibili |
| `/api/llm/config` | POST | JSON | Cambia provider/modello LLM a runtime |
| `/api/quick-scan?url=...` | GET | SSE Stream | Scansione rapida con streaming |
| `/api/scan-full/stream?url=...&competitor_url=...&keywords=...` | GET | SSE Stream | Scansione completa con competitor |
| `/api/agent-scan` | POST | JSON | Audit avanzato orchestrato |
| `/api/agent-scan/stream?url=...` | GET | SSE Stream | Audit avanzato con streaming |
| `/api/chat` | POST | SSE Stream | **AI Chat con RAG** — streaming token-by-token |
| `/api/chat/history?conversation_id=...` | GET | JSON | Cronologia conversazione |
| `/api/chat/clear` | POST | JSON | Cancella cronologia conversazione |

---

## 🛠️ Stack Tecnologico

### Backend
| Tecnologia | Ruolo |
|-----------|-------|
| **FastAPI** | Web framework + SSE streaming |
| **LangChain** + **Multi-LLM** | AI agents, fix generation, report (OpenAI/Anthropic/Mistral/Ollama) |
| **ChromaDB** | Vector database persistente per RAG |
| **OpenAI Embeddings** | text-embedding-3-small per retrieval |
| **BeautifulSoup** + **lxml** | HTML parsing e scraping |
| **HTTPX** | HTTP client asincrono |
| **Playwright** | Browser-based scraping (JS rendering) |
| **scikit-learn** | TF-IDF keyword clustering |
| **Tavily Search** | Competitor discovery |

### Frontend
| Tecnologia | Ruolo |
|-----------|-------|
| **Next.js 16** (App Router) | Framework React con SSR |
| **React 19** | UI library |
| **TypeScript 5** | Type safety |
| **Tailwind CSS 4** | Styling utility-first |
| **Recharts** | Grafici (radar, bar, progress) |
| **react-markdown** | Rendering report Markdown |
| **html2pdf.js** | Export PDF client-side |

---

## 📊 Cosa Analizza SEO-PRO

### 22+ Regole SEO Implementate

| Categoria | Checks |
|-----------|--------|
| **Meta & Title** | Title (missing/short/long), Meta description (missing/short/long), Meta robots |
| **Content** | H1 (missing/multiple/mismatch), Heading hierarchy, Content length, Keyword density |
| **Technical** | HTTPS, Canonical, Robots.txt, Sitemap.xml, Viewport, Lang attribute |
| **Images** | ALT text missing, Image optimization |
| **Social** | Open Graph tags, Twitter Card |
| **Links** | Internal links count, External links, Broken links |
| **Performance** | Page size, Script count, Compression (gzip/br) |
| **Security** | API key exposure, Mixed content, Security headers |
| **Schema** | JSON-LD structured data |

### AI-Powered Reports

| Report | Contenuto |
|--------|-----------|
| 🔧 **AutoFix** | Fix tecnici con codice pronto da implementare |
| 🏷️ **Schema Markup** | JSON-LD generato + guida implementazione |
| 📝 **Content Expansion** | Contenuto SEO-optimized con keyword integration |
| 📋 **Roadmap** | Piano d'azione con priorità e timeline |
| ⚔️ **Strategy** | Strategia competitiva con action plan |
| 📊 **Full Report** | Audit Markdown completo generato da LLM |

---

## 🗺️ Roadmap

- [x] Quick Scan con SSE streaming
- [x] Full Scan con competitor + keywords
- [x] Advanced AI Audit orchestrato
- [x] Autonomous Mode (ReAct agent)
- [x] PDF export client-side
- [x] SEO Knowledge Base
- [x] **RAG Phase 1**: Knowledge Base indicizzata in ChromaDB + context augmentation su AI fixes
- [x] **RAG Phase 2**: Storico scansioni in ChromaDB + AI Chat con retrieval multi-collection
- [x] **AI Chat**: Chat interattiva con streaming, memoria conversazionale e suggerimenti
- [x] **Multi-LLM Provider**: Supporto OpenAI, Anthropic (Claude), Mistral (Devstral), Ollama (Llama) con switch a runtime dalla dashboard
- [ ] Dashboard storica con trend scansioni
- [ ] Multi-page crawl (intero sito)
- [ ] Scan scheduling (cron)
- [ ] User accounts e autenticazione
- [ ] API versioning (v1)
- [ ] Integrazione Google Search Console
- [ ] Docker containerizzazione
- [ ] Multi-lingua (i18n)
- [ ] PWA per accesso mobile

---

## � RAG Architecture (Retrieval-Augmented Generation)

SEO-PRO utilizza un sistema RAG a due livelli per potenziare la qualità delle risposte AI:

### Phase 1 — Knowledge Base RAG
- **34 documenti SEO** indicizzati in ChromaDB (fondamenti, tecnica, contenuti, performance, sicurezza, strategie avanzate, strumenti)
- **Indicizzazione automatica** all'avvio del server 
- **Context augmentation** sui prompt di AI AutoFix e Fix Suggestions
- **Embeddings**: OpenAI `text-embedding-3-small` 

### Phase 2 — Scan History RAG + AI Chat
- **Ogni scansione** viene persistita in ChromaDB con sezioni granulari (overview, errors, technical, performance, authority, autofix, roadmap)
- **AI Chat** con retrieval multi-collection: interroga sia la knowledge base che lo storico scansioni
- **3 livelli di contesto**: dati scan corrente → knowledge base → storico scansioni
- **Memoria conversazionale** per follow-up coerenti (ultime 20 interazioni)
- **Streaming token-by-token** per esperienza chat in tempo reale

### Come funziona

```
[User Question] → [Embed Query] → [ChromaDB Query]
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            [seo_knowledge]     [scan_results]     [conversation]
            34 documenti        storico scans       memoria chat
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                              [Augmented Prompt]
                                        ▼
                              [GPT-4o-mini + RAG]
                                        ▼
                              [Streaming Response]
```

---

## �🤝 Contribuire

I contributi sono benvenuti! Ecco come partecipare:

1. **Fork** il repository
2. Crea un **branch** per la feature (`git checkout -b feature/nuova-feature`)
3. **Committa** le modifiche (`git commit -m 'Add: nuova feature'`)
4. **Pusha** il branch (`git push origin feature/nuova-feature`)
5. Apri una **Pull Request**



## 📄 Licenza

Distribuito sotto licenza **MIT**. Vedi [LICENSE](LICENSE) per maggiori informazioni.

---

##  Strumenti utilizzati 

- [FastAPI](https://fastapi.tiangolo.com) — Web framework Python ad alte prestazioni
- [Next.js](https://nextjs.org) — Framework React per la produzione
- [LangChain](https://langchain.com) — Framework per applicazioni LLM
- [OpenAI](https://openai.com) — Modelli GPT per generazione intelligente
- [Tailwind CSS](https://tailwindcss.com) — Framework CSS utility-first
- [Recharts](https://recharts.org) — Libreria grafici React

---





