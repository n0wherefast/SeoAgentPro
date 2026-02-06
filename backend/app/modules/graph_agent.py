"""
Graph agent module - Workflow orchestrator for SEO audits
Ported from SEO-AGENT/graph_agent.py (simplified version without langgraph dependency)
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Import tools from consolidated graph_tools module
from app.modules.graph_tools import (
    detect_seo_issues_pure,
    generate_fixes_pure,
    analyze_security_pure,
    analyze_competitors_pure,
    calculate_seo_score,
)
from app.modules.scraper import smart_scrape_url
from app.modules.seo_technical import analyze_sitemap
from app.core.llm_factory import get_shared_llm


class GraphAuditOrchestrator:
    """
    Simplified workflow orchestrator for SEO audits.
    Replaces LangGraph for simpler dependency management.
    """
    
    def __init__(self):
        self.state = {}
        self.logger = None

    def _log(self, step: str, message: str, tool: str = "", status: str = "running"):
        entry = {
            "step": step,
            "message": message,
            "tool": tool,
            "status": status,
        }
        self.state.setdefault("logs", []).append(entry)
        if self.logger:
            self.logger(entry)
    
    def run_audit(self, url: str, competitor_count: int = 3, focus: str = "general") -> Dict[str, Any]:
        """
        Execute complete SEO audit workflow.
        
        Steps:
        1. Fetch page HTML
        2. Extract SEO elements
        3. Analyze for issues
        4. Research competitors
        5. Generate fixes
        6. Compile report
        """
        
        # Initialize state
        self.state = {
            "url": url,
            "focus": focus,
            "competitor_count": competitor_count,
            "html_content": "",
            "seo_data": {},
            "issues": [],
            "fixes": [],
            "competitors": [],
            "seo_score": 0,
            "final_report_md": ""
        }

        # 1. FETCH + EXTRACT (tool unico)
        self._log("fetch", f"Fetching {url}", "smart_scrape_url")
        scraped = smart_scrape_url(url)
        err = scraped.get("error") if isinstance(scraped, dict) else None
        if err:
            self.state["fetch_error"] = err
            self._log("fetch", err, "smart_scrape_url", status="error")
        html = scraped.pop("html_content", "") if isinstance(scraped, dict) else ""
        self.state["html_content"] = html
        self.state["seo_data"] = scraped if isinstance(scraped, dict) else {}
        if not err:
            self._log("fetch", "Fetch completato", "smart_scrape_url", status="done")

        self._log("extract", "Estrazione elementi SEO", "smart_scrape_url")
        self._log("extract", "Estrazione completata", "smart_scrape_url", status="done")
        
        # 3. ANALYZE
        seo_data = self.state["seo_data"]
        self._log("analyze", "Analisi issues e sicurezza", "detect_seo_issues_pure")
        issues = detect_seo_issues_pure(seo_data)
        issues.extend(analyze_security_pure(self.state["html_content"]))
        score = calculate_seo_score(issues)
        self.state["issues"] = issues
        self.state["seo_score"] = score
        self._log("analyze", f"Analisi completata, score {score}", "detect_seo_issues_pure", status="done")
        
        # 4. COMPETITORS
        self._log("competitors", "Analisi competitor", "analyze_competitors_pure")
        title = seo_data.get("title", "")
        keyword = " ".join(title.split()[:3]) if title else "homepage"
        competitors = analyze_competitors_pure(keyword, url, limit=competitor_count, seo_data=seo_data)
        self.state["competitors"] = competitors
        self._log("competitors", f"Trovati {len(competitors)} competitor", "analyze_competitors_pure", status="done")
        
        # 5. FIXES
        self._log("fixes", "Generazione fix AI", "generate_fixes_pure")
        text_sample = seo_data.get("text_sample", "")
        tech_stack = seo_data.get("tech_stack", "HTML/Custom")
        if issues:
            fixes = generate_fixes_pure(issues, user_url=url, text_sample=text_sample, tech_stack=tech_stack)
            self.state["fixes"] = fixes
        self._log("fixes", f"Fix generati: {len(self.state.get('fixes', []))}", "generate_fixes_pure", status="done")
        
        # 6. REPORT
        self._log("report", "Compilazione report", "llm")
        self._generate_report()
        self._log("report", "Report pronto", "llm", status="done")
        
        # 7. STORE IN RAG
        try:
            from app.modules.scan_store import store_scan_result
            store_scan_result(
                url=url,
                scraped=self.state.get("seo_data", {}),
                errors=self.state.get("issues", []),
                seo_score={"score": self.state.get("seo_score", 0)},
                technical=self.state.get("seo_data", {}),
                ai_autofix=json.dumps(self.state.get("fixes", []), ensure_ascii=False)[:3000],
                ai_roadmap=self.state.get("final_report_md", "")[:3000],
            )
        except Exception as e:
            logger.error("Failed to store graph scan in RAG: %s", e)
        
        return self.state

    def run_audit_stream(self, url: str, competitor_count: int = 3, focus: str = "general"):
        """Generator that yields SSE-friendly log events plus final data."""
        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        # Initialize state
        self.state = {
            "url": url,
            "focus": focus,
            "competitor_count": competitor_count,
            "html_content": "",
            "seo_data": {},
            "issues": [],
            "fixes": [],
            "competitors": [],
            "seo_score": 0,
            "final_report_md": "",
            "logs": [],
        }

        try:
            # Fetch + Extract (tool unico)
            self._log("fetch", f"Fetching {url}", "smart_scrape_url")
            yield sse("log", self.state["logs"][-1])
            scraped = smart_scrape_url(url)
            err = scraped.get("error") if isinstance(scraped, dict) else None
            if err:
                self.state["fetch_error"] = err
                self._log("fetch", err, "smart_scrape_url", status="error")
                yield sse("log", self.state["logs"][-1])
            html = scraped.pop("html_content", "") if isinstance(scraped, dict) else ""
            self.state["html_content"] = html
            self.state["seo_data"] = scraped if isinstance(scraped, dict) else {}
            if not err:
                self._log("fetch", "Fetch completato", "smart_scrape_url", status="done")
                yield sse("log", self.state["logs"][-1])

            self._log("extract", "Estrazione elementi SEO", "smart_scrape_url")
            yield sse("log", self.state["logs"][-1])
            self._log("extract", "Estrazione completata", "smart_scrape_url", status="done")
            yield sse("log", self.state["logs"][-1])

            # Sitemap analysis (streamed): se presente una sitemap_url, analizzala e invia evento separato
            try:
                _seo = self.state.get("seo_data", {})
                sitemap_url = _seo.get("sitemap_url") if isinstance(_seo, dict) else None
                if sitemap_url:
                    sitemap_analysis = analyze_sitemap(sitemap_url)
                    self.state["sitemap_analysis"] = sitemap_analysis
                    yield sse("sitemap_analysis", sitemap_analysis)
                    # anche log dell'operazione
                    self._log("sitemap", f"Sitemap analysis inviata per {sitemap_url}", "analyze_sitemap", status="done")
                    yield sse("log", self.state["logs"][-1])
            except Exception as e:
                self._log("sitemap", f"Errore sitemap analysis: {str(e)}", "analyze_sitemap", status="error")
                yield sse("log", self.state["logs"][-1])

            # Analyze
            self._log("analyze", "Analisi issues e sicurezza", "detect_seo_issues_pure")
            yield sse("log", self.state["logs"][-1])
            issues = detect_seo_issues_pure(self.state.get("seo_data", {}))
            issues.extend(analyze_security_pure(self.state.get("html_content", "")))
            score = calculate_seo_score(issues)
            self.state["issues"] = issues
            self.state["seo_score"] = score
            self._log("analyze", f"Analisi completata, score {score}", "detect_seo_issues_pure", status="done")
            yield sse("log", self.state["logs"][-1])

            # Send intermediate data events
            yield sse("scrape", self.state.get("seo_data", {}))
            logger.debug("Sending onpage_errors with %d issues: %s", len(issues), issues[:2] if issues else "empty")
            yield sse("onpage_errors", issues)
            yield sse("seo_score", {"score": score})

            # Competitors
            self._log("competitors", "Analisi competitor", "analyze_competitors_pure")
            yield sse("log", self.state["logs"][-1])
            _seo_for_comp = self.state.get("seo_data", {})
            title = _seo_for_comp.get("title", "")
            keyword = " ".join(title.split()[:3]) if title else "homepage"
            competitors = analyze_competitors_pure(keyword, url, limit=competitor_count, seo_data=_seo_for_comp)
            self.state["competitors"] = competitors
            self._log("competitors", f"Trovati {len(competitors)} competitor", "analyze_competitors_pure", status="done")
            yield sse("log", self.state["logs"][-1])
            yield sse("competitors", competitors)

            # Fixes
            self._log("fixes", "Generazione fix AI", "generate_fixes_pure")
            yield sse("log", self.state["logs"][-1])
            text_sample = self.state.get("seo_data", {}).get("text_sample", "")
            tech_stack = self.state.get("seo_data", {}).get("tech_stack", "HTML/Custom")
            if issues:
                fixes = generate_fixes_pure(issues, user_url=url, text_sample=text_sample, tech_stack=tech_stack)
                self.state["fixes"] = fixes
            self._log("fixes", f"Fix generati: {len(self.state.get('fixes', []))}", "generate_fixes_pure", status="done")
            yield sse("log", self.state["logs"][-1])
            logger.debug("Sending fixes with %d fixes: %s", len(self.state.get("fixes", [])), self.state.get("fixes", [])[:2] if self.state.get("fixes") else "empty")
            yield sse("fixes", self.state.get("fixes", []))

            # Report
            self._log("report", "Compilazione report", "llm")
            yield sse("log", self.state["logs"][-1])
            self._generate_report()
            self._log("report", "Report pronto", "llm", status="done")
            yield sse("log", self.state["logs"][-1])
            report_content = self.state.get("final_report_md", "")
            logger.debug("Report generated, length: %d, first 200 chars: %s", len(report_content), report_content[:200])
            yield sse("report", {"content": report_content})

            # Store scan in ChromaDB for RAG
            stored_scan_id = None
            try:
                from app.modules.scan_store import store_scan_result
                from urllib.parse import urlparse
                seo_data = self.state.get("seo_data", {})
                stored_scan_id = store_scan_result(
                    url=url,
                    scraped=seo_data,
                    errors=self.state.get("issues", []),
                    seo_score={"score": self.state.get("seo_score", 0)},
                    technical=seo_data,  # graph scan seo_data includes technical info
                    ai_autofix=json.dumps(self.state.get("fixes", []), ensure_ascii=False)[:3000],
                    ai_roadmap=report_content[:3000] if report_content else None,
                )
                self._log("storage", f"Scan stored in RAG: {stored_scan_id}", "scan_store", status="done")
                yield sse("log", self.state["logs"][-1])
            except Exception as e:
                logger.error("Failed to store graph scan in RAG: %s", e)

            # Done — include scan_id for frontend localStorage
            done_payload = {
                "url": url,
                "seo_score": self.state.get("seo_score"),
                "seo_data": self.state.get("seo_data"),
                "issues": self.state.get("issues"),
                "fixes": self.state.get("fixes"),
                "competitors": self.state.get("competitors"),
                "report": self.state.get("final_report_md"),
                "sitemap_analysis": self.state.get("sitemap_analysis"),
            }
            if stored_scan_id:
                done_payload["scan_id"] = stored_scan_id
            yield sse("done", done_payload)
        except Exception as e:
            self._log("stream", f"Errore stream: {str(e)}", "run_audit_stream", status="error")
            if self.state.get("logs"):
                yield sse("log", self.state["logs"][-1])
            yield sse("error", {"message": str(e)})
            yield sse("done", {"error": str(e)})
            return
    
    def _generate_report(self):
        """Generate final Markdown report using LLM."""
        
        data = self.state.get("seo_data", {})
        issues = self.state.get("issues", [])
        fixes = self.state.get("fixes", [])
        competitors = self.state.get("competitors", [])
        score = self.state.get("seo_score", 0)
        url = self.state.get("url")
        
        security_issues = [i for i in issues if i.get("category") == "security"]
        api_key_status = f"❌ ATTENZIONE: Rilevate {len(security_issues)} chiavi esposte." if security_issues else "✅ Nessuna API Key esposta."
        headings_data = data.get('headings', {})
        h1_count = len(headings_data.get('h1', [])) if isinstance(headings_data, dict) else 0

        context_str = f"""
# ================================
# 📄 INPUT CONTEXT FOR SEO AUDIT
# ================================

# 1. CORE INFO & METRICS
URL: {url}
TECH_STACK: {data.get('tech_stack', 'N/A')}
SEO_SCORE: {score}/100
ISSUES_COUNT: {len(issues)}
FIX_PROPOSALS_COUNT: {len(fixes)}

# 2. SECURITY & PERFORMANCE
- HTTPS Active: {data.get('has_https')}
- API Security Check: {api_key_status}
- Compression: {data.get('compression')}
- Page Size: {data.get('page_size_kb')} KB
- Scripts Loaded: {data.get('scripts_count')}

# 3. ON-PAGE META DATA
- Title: {data.get('title')} (Len: {len(data.get('title') or '')})
- Meta Description: {data.get('meta_description')}
- Robots: {data.get('robots')}
- Canonical: {data.get('canonical')}
- Keywords Found: {data.get('keywords')}
- Favicon: {data.get('favicon')}
- HTML Lang: {data.get('html_lang')}
- Viewport: {data.get('meta_viewport')}

# 4. CONTENT & STRUCTURE
- Word Count: {data.get('word_count')}
- Text/HTML Ratio: {data.get('text_ratio')}%
- H1 Count: {h1_count}
- Headings Structure: {json.dumps(headings_data, ensure_ascii=False)}
- Paragraphs Sample: {json.dumps(data.get('paragraphs', [])[:3], ensure_ascii=False)} 
- Structured Data Present: {data.get('structured_data_present')}

# 5. IMAGES & MEDIA
- Total Images: {data.get('images_count')}
- Missing Alt: {data.get('missing_alt_count')}
- Images List (JSON): {json.dumps(data.get('images', []), ensure_ascii=False)}

# 6. LINKS PROFILE
- Internal Links Count: {data.get('links_internal')}
- External Links Count: {data.get('links_external')}
- Links Data (JSON): {json.dumps(data.get('links', []), ensure_ascii=False)}

# 7. SOCIAL GRAPH
- Twitter Card: {json.dumps(data.get('twitter_card', {}), ensure_ascii=False)}
- Open Graph / Social Tags: {json.dumps(data.get('social_tags', {}), ensure_ascii=False)}

# ================================
# 🚨 ANALYSIS RESULTS (Generated by Auditor)
# ================================

Detected Issues:
{json.dumps(issues, ensure_ascii=False, indent=2)}

Proposed Fixes (Code/Action):
{json.dumps(fixes, ensure_ascii=False, indent=2)}

Competitors Analysis:
{json.dumps(competitors, ensure_ascii=False, indent=2)}
"""

        system_msg = """Sei un Senior SEO Auditor esperto in Technical SEO e Content Analysis. 
Analizza i dati forniti e genera un report DETTAGLIATO in Markdown seguendo rigorosamente questa struttura.
Usa icone ed elenchi puntati per mantenere alta la leggibilità.

# 🚀 SEO Audit Report: {title}
**Data Audit:** [DATA ODIERNA]
**Tech Stack:** [Tech Stack rilevato] | **Page Size:** [page_size_kb] KB | **HTTPS:** [Sì/No]

## 🧠 Executive Summary
- **SEO Score Stimato:** **[Score]/100**
- **Stato Scansione:** Robots: [robots] | Canonical: [canonical]
- **Problemi Critici:** [COUNT]
- **Fix Rapidi:** [COUNT]

(Scrivi un breve paragrafo riassuntivo di 3 righe sullo stato generale della pagina)

---

## 🔍 Analisi On-Page & Contenuto
Valutazione della qualità dei contenuti e dei meta tag.

| Elemento | Stato | Dettagli / Valore |
| :--- | :--- | :--- |
| **Meta Title** | [✅/⚠️/❌] | [Lunghezza caratteri] |
| **Meta Desc** | [✅/⚠️/❌] | [Presenza e Lunghezza] |
| **H1 Tag** | [✅/⚠️/❌] | [Contenuto H1 o "Mancante"] |
| **Word Count** | ℹ️ | [word_count] parole (Text Ratio: [text_ratio]%) |
| **Immagini** | [✅/⚠️] | Totali: [images_count] | Senza ALT: [missing_alt_count] |
| **Lingua HTML** | ℹ️ | [html_lang] |

**Analisi Headings:**
[Analisi gerarchia H2-H6 basata su 'headings']

---

## ⚙️ Performance & Tecnica
Analisi dei fattori tecnici che influenzano ranking e UX.

- **Mobile Friendly:** Viewport [meta_viewport]
- **Compressione:** [compression]
- **Script Caricati:** [scripts_count] scripts
- **Dati Strutturati:** [structured_data_present] (Schema.org)
- **Sicurezza:** HTTPS [has_https]

---

## 🔗 Link Profile & Social
Panoramica della connettività e della presenza social.

- **Internal Links:** [links_internal]
- **External Links:** [links_external]
- **Social Cards:** 
  - Twitter: [Sì/No] (Card type: [twitter_card type])
  - Open Graph: [Sì/No] (Tags rilevati)

---

## 🚨 Problemi Rilevati & Soluzioni
Elenca i problemi specifici trovati nei dati (es. ALT mancanti, title troppo lungo, ratio testo basso).

| Priorità | Problema | Soluzione Tecnica |
| :--- | :--- | :--- |
| 🔴 Alta | [Problema] | `[Codice/Soluzione]` |
| 🟡 Media | [Problema] | `[Codice/Soluzione]` |

---

## ⚔️ Competitor & Keyword Analysis
Analisi basata sulle keywords rilevate: [keywords]
- [Lista Competitor potenziali]

---

## 🛠️ Action Plan Finale
I 3 passaggi chiave da implementare subito.
1. [Azione 1]
2. [Azione 2]
3. [Azione 3]
"""

        
        from langchain_core.messages import SystemMessage, HumanMessage
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        try:
            llm = get_shared_llm()
            response = llm.invoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=f"Data: {current_date}\nDati:\n{context_str}")
            ])
            self.state["final_report_md"] = response.content
        except Exception as e:
            self.state["final_report_md"] = f"# Report Error\n{str(e)}"


# Factory function for compatibility
def create_audit_orchestrator():
    """Create and return an orchestrator instance."""
    return GraphAuditOrchestrator()


# ==============================================================================
# UNIFIED SCAN ORCHESTRATOR - Mode-based Workflow Engine
# ==============================================================================

class UnifiedScanOrchestrator(GraphAuditOrchestrator):
    """
    Extended orchestrator with mode-based workflows.
    
    Modes:
    - quick: Fast scan (scrape + detect + score)
    - full: Complete scan (+ technical + performance + fixes)
    - advanced: Full audit (+ competitors + AI strategy + roadmap)
    """
    
    MODES = {
        "quick": ["scrape", "detect_issues", "score"],
        "full": ["scrape", "detect_issues", "technical", "performance", "score", "fixes", "report"],
        "advanced": ["scrape", "detect_issues", "technical", "performance", 
                     "competitors", "score", "fixes", "strategy", "roadmap", "report"],
        "autonomous": "react_loop"  # AI-driven adaptive workflow
    }
    
    def execute(self, url: str, mode: str = "full", options: dict = None):
        """
        Execute workflow based on mode.
        
        Args:
            url: Target URL to scan
            mode: Workflow mode (quick/full/advanced/autonomous)
            options: Additional options (competitor_url, keywords, max_iterations, etc)
        """
        options = options or {}
        
        # Handle autonomous mode separately
        if mode == "autonomous":
            from app.modules.agents.react_orchestrator import ReActOrchestrator
            max_iterations = options.get("max_iterations", 8)
            orchestrator = ReActOrchestrator(max_iterations=max_iterations)
            return orchestrator.execute(url, options)
        
        # Initialize state for sequential modes
        self.state = {
            "url": url,
            "mode": mode,
            "options": options,
            "html_content": "",
            "seo_data": {},
            "issues": [],
            "fixes": [],
            "competitors": [],
            "seo_score": 0,
            "final_report_md": "",
            "logs": []
        }
        
        # Get workflow nodes for mode
        nodes = self.MODES.get(mode, self.MODES["full"])
        
        # Initialize agents based on options
        agents = self._initialize_agents(options)
        
        # Execute workflow
        for node in nodes:
            self._execute_node(node, agents)
        
        return self.state
    
    def execute_stream(self, url: str, mode: str = "full", options: dict = None):
        """
        Execute workflow with SSE streaming.
        """
        options = options or {}
        
        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"
        
        # Handle autonomous mode with streaming
        if mode == "autonomous":
            from app.modules.agents.react_orchestrator import ReActOrchestrator
            max_iterations = options.get("max_iterations", 8)
            orchestrator = ReActOrchestrator(max_iterations=max_iterations)
            
            # Stream directly from ReActOrchestrator (includes all events)
            for event in orchestrator.execute_stream(url, options):
                yield event
            return
        
        # Initialize state for sequential modes
        self.state = {
            "url": url,
            "mode": mode,
            "options": options,
            "html_content": "",
            "seo_data": {},
            "issues": [],
            "fixes": [],
            "competitors": [],
            "seo_score": 0,
            "final_report_md": "",
            "logs": []
        }
        
        # Get workflow nodes
        nodes = self.MODES.get(mode, self.MODES["full"])
        
        # Initialize agents
        agents = self._initialize_agents(options)
        
        # Execute workflow with streaming
        for node in nodes:
            try:
                self._log(node, f"Executing {node}")
                yield sse("log", self.state["logs"][-1])
                
                self._execute_node(node, agents)
                
                self._log(node, f"{node} complete", status="done")
                yield sse("log", self.state["logs"][-1])
                
                # Stream intermediate results
                if node == "scrape":
                    yield sse("scrape", self.state.get("seo_data", {}))
                elif node == "detect_issues":
                    yield sse("onpage_errors", self.state.get("issues", []))
                elif node == "technical":
                    yield sse("technical", self.state.get("technical_data", {}))
                elif node == "performance":
                    yield sse("performance", self.state.get("performance_data", {}))
                elif node == "score":
                    yield sse("seo_score", {"score": self.state.get("seo_score", 0)})
                elif node == "fixes":
                    yield sse("fixes", self.state.get("fixes", []))
                elif node == "competitors":
                    yield sse("competitors", self.state.get("competitors", []))
                elif node == "report":
                    yield sse("report", {"content": self.state.get("final_report_md", "")})
            except Exception as e:
                import traceback
                error_msg = f"Error in node {node}: {str(e)}"
                logger.error("%s", error_msg)
                traceback.print_exc()
                self._log(node, error_msg, status="error")
                yield sse("log", self.state["logs"][-1])
        
        # Final result
        final_data = {
            "url": url,
            "mode": mode,
            "seo_score": self.state.get("seo_score"),
            "seo_data": self.state.get("seo_data"),
            "issues": self.state.get("issues"),
            "fixes": self.state.get("fixes"),
            "report": self.state.get("final_report_md")
        }
        logger.info("Sending done event with data keys: %s", final_data.keys())
        yield sse("done", final_data)
    
    def _initialize_agents(self, options: dict) -> dict:
        """
        Initialize agents based on options.
        """
        agents = {}
        
        # Conditionally load agents only if needed
        if options.get("use_authority_agent"):
            from app.modules.agents.authority_agent import AuthorityAgent
            agents["authority"] = AuthorityAgent()
        
        if options.get("keywords") or options.get("target_keywords"):
            from app.modules.agents.keyword_agent import KeywordAgent
            agents["keyword"] = KeywordAgent()
        
        return agents
    
    def _execute_node(self, node: str, agents: dict):
        """
        Execute a single workflow node.
        """
        if node == "scrape":
            self._node_scrape()
        elif node == "detect_issues":
            self._node_detect_issues()
        elif node == "technical":
            self._node_technical()
        elif node == "performance":
            self._node_performance()
        elif node == "score":
            self._node_score()
        elif node == "fixes":
            self._node_fixes()
        elif node == "competitors":
            self._node_competitors()
        elif node == "strategy":
            self._node_strategy(agents)
        elif node == "roadmap":
            self._node_roadmap()
        elif node == "report":
            self._node_report()
    
    # Node implementations
    def _node_scrape(self):
        """Scrape URL and extract SEO data."""
        from app.modules.scraper import smart_scrape_url
        
        url = self.state.get("url")
        scraped = smart_scrape_url(url)
        self.state["seo_data"] = scraped
    
    def _node_detect_issues(self):
        """Detect SEO issues."""
        from app.modules.seo_detection_unified import detect_seo_issues_unified
        
        scraped = self.state.get("seo_data", {})
        issues = detect_seo_issues_unified(scraped)
        self.state["issues"] = issues
    
    def _node_technical(self):
        """Run technical checks."""
        from app.modules.seo_technical import run_technical_checks
        
        scraped = self.state.get("seo_data", {})
        url = self.state.get("url")
        technical = run_technical_checks(scraped, url)
        
        self.state["technical_data"] = technical
        self.state["issues"].extend(technical.get("technical_errors", []))
    
    def _node_performance(self):
        """Run performance analysis."""
        from app.modules.competitor.lighthouse_client import run_performance_engine
        
        url = self.state.get("url")
        try:
            performance = run_performance_engine(url)
            self.state["performance_data"] = performance
        except Exception as e:
            self.state["performance_data"] = {"error": str(e)}
    
    def _node_score(self):
        """Calculate SEO score."""
        from app.modules.seo_rules import SEOScoringEngine
        
        issues = self.state.get("issues", [])
        perf_score = self.state.get("performance_data", {}).get("performance_score")
        
        engine = SEOScoringEngine(issues, performance_score=perf_score)
        self.state["seo_score"] = engine.weighted_total_score()
    
    def _node_fixes(self):
        """Generate AI fixes."""
        from app.modules.ai_fix_agents import generate_fix_suggestions
        
        issues = self.state.get("issues", [])
        scraped = self.state.get("seo_data", {})
        
        if issues:
            fixes = generate_fix_suggestions(issues, scraped)
            self.state["fixes"] = fixes
    
    def _node_competitors(self):
        """Analyze competitors."""
        from app.modules.graph_tools import analyze_competitors_pure
        
        scraped = self.state.get("seo_data", {})
        url = self.state.get("url")
        
        title = scraped.get("title", "")
        keyword = " ".join(title.split()[:3]) if title else "homepage"
        
        competitor_count = self.state.get("options", {}).get("competitor_count", 3)
        competitors = analyze_competitors_pure(keyword, url, limit=competitor_count)
        
        self.state["competitors"] = competitors
    
    def _node_strategy(self, agents: dict):
        """Generate AI strategy using AuthorityAgent if available."""
        authority_agent = agents.get("authority")
        
        if authority_agent:
            your_scan = self.state.get("seo_data", {})
            # Get first competitor if available
            competitors = self.state.get("competitors", [])
            comp_scan = competitors[0] if competitors else None
            
            result = authority_agent.execute({
                "your_scan": your_scan,
                "competitor_scan": comp_scan
            })
            
            self.state["authority_analysis"] = result
    
    def _node_roadmap(self):
        """Generate AI roadmap."""
        from app.modules.ai_roadmap_agent import generate_roadmap
        
        issues = self.state.get("issues", [])
        scraped = self.state.get("seo_data", {})
        
        roadmap = generate_roadmap(issues, scraped)
        self.state["roadmap"] = roadmap

    def _node_report(self):
        """Generate final markdown report using parent's _generate_report method."""
        self._generate_report()

