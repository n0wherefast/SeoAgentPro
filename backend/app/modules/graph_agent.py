"""
Graph agent module - Workflow orchestrator for SEO audits
Ported from SEO-AGENT/graph_agent.py (simplified version without langgraph dependency)
"""

import json
from datetime import datetime
from typing import Dict, Any, List

# Import tools from consolidated graph_tools module
from app.modules.graph_tools import (
    extract_seo_elements_pure,
    detect_seo_issues_pure,
    fetch_page_pure,
    generate_fixes_pure,
    analyze_security_pure,
    analyze_competitors_pure,
    calculate_seo_score,
)
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
        
        # 1. FETCH
        self._log("fetch", f"Fetching {url}", "fetch_page_pure")
        html = fetch_page_pure(url)
        if html.startswith("ERROR:"):
            self.state["final_report_md"] = f"# Errore Fatale\n{html}"
            self._log("fetch", html, "fetch_page_pure", status="error")
            return self.state
        self.state["html_content"] = html
        self._log("fetch", "Fetch completato", "fetch_page_pure", status="done")
        
        # 2. EXTRACT
        self._log("extract", "Estrazione elementi SEO", "extract_seo_elements_pure")
        seo_data = extract_seo_elements_pure(html, url)
        self.state["seo_data"] = seo_data
        self._log("extract", "Estrazione completata", "extract_seo_elements_pure", status="done")
        
        # 3. ANALYZE
        self._log("analyze", "Analisi issues e sicurezza", "detect_seo_issues_pure")
        issues = detect_seo_issues_pure(seo_data)
        issues.extend(analyze_security_pure(html))
        score = calculate_seo_score(issues)
        self.state["issues"] = issues
        self.state["seo_score"] = score
        self._log("analyze", f"Analisi completata, score {score}", "detect_seo_issues_pure", status="done")
        
        # 4. COMPETITORS
        self._log("competitors", "Analisi competitor", "analyze_competitors_pure")
        title = seo_data.get("title", "")
        keyword = " ".join(title.split()[:3]) if title else "homepage"
        competitors = analyze_competitors_pure(keyword, url, limit=competitor_count)
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

        # Fetch
        self._log("fetch", f"Fetching {url}", "fetch_page_pure")
        yield sse("log", self.state["logs"][-1])
        html = fetch_page_pure(url)
        if html.startswith("ERROR:"):
            self._log("fetch", html, "fetch_page_pure", status="error")
            yield sse("log", self.state["logs"][-1])
            yield sse("done", {"error": html})
            return
        self.state["html_content"] = html
        self._log("fetch", "Fetch completato", "fetch_page_pure", status="done")
        yield sse("log", self.state["logs"][-1])

        # Extract
        self._log("extract", "Estrazione elementi SEO", "extract_seo_elements_pure")
        yield sse("log", self.state["logs"][-1])
        seo_data = extract_seo_elements_pure(html, url)
        self.state["seo_data"] = seo_data
        self._log("extract", "Estrazione completata", "extract_seo_elements_pure", status="done")
        yield sse("log", self.state["logs"][-1])

        # Sitemap analysis (streamed): se presente una sitemap_url, analizzala e invia evento separato
        try:
            sitemap_url = seo_data.get("sitemap_url") if isinstance(seo_data, dict) else None
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
        issues = detect_seo_issues_pure(seo_data)
        issues.extend(analyze_security_pure(html))
        score = calculate_seo_score(issues)
        self.state["issues"] = issues
        self.state["seo_score"] = score
        self._log("analyze", f"Analisi completata, score {score}", "detect_seo_issues_pure", status="done")
        yield sse("log", self.state["logs"][-1])

        # Competitors
        self._log("competitors", "Analisi competitor", "analyze_competitors_pure")
        yield sse("log", self.state["logs"][-1])
        title = seo_data.get("title", "")
        keyword = " ".join(title.split()[:3]) if title else "homepage"
        competitors = analyze_competitors_pure(keyword, url, limit=competitor_count)
        self.state["competitors"] = competitors
        self._log("competitors", f"Trovati {len(competitors)} competitor", "analyze_competitors_pure", status="done")
        yield sse("log", self.state["logs"][-1])

        # Fixes
        self._log("fixes", "Generazione fix AI", "generate_fixes_pure")
        yield sse("log", self.state["logs"][-1])
        text_sample = seo_data.get("text_sample", "")
        tech_stack = seo_data.get("tech_stack", "HTML/Custom")
        if issues:
            fixes = generate_fixes_pure(issues, user_url=url, text_sample=text_sample, tech_stack=tech_stack)
            self.state["fixes"] = fixes
        self._log("fixes", f"Fix generati: {len(self.state.get('fixes', []))}", "generate_fixes_pure", status="done")
        yield sse("log", self.state["logs"][-1])

        # Report
        self._log("report", "Compilazione report", "llm")
        yield sse("log", self.state["logs"][-1])
        self._generate_report()
        self._log("report", "Report pronto", "llm", status="done")
        yield sse("log", self.state["logs"][-1])

        # Done
        yield sse(
            "done",
            {
                "url": url,
                "seo_score": self.state.get("seo_score"),
                "seo_data": self.state.get("seo_data"),
                "issues": self.state.get("issues"),
                "fixes": self.state.get("fixes"),
                "competitors": self.state.get("competitors"),
                "report": self.state.get("final_report_md"),
            },
        )
    
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
        
        context_str = f"""
        URL: {url}
        STACK: {data.get('tech_stack', 'N/A')}
        SCORE: {score}/100
        ISSUES_COUNT: {len(issues)}
        FIX_COUNT: {len(fixes)}

        SECURITY STATUS:
        - HTTPS: {data.get('has_https')}
        - API_ANALYSIS_RESULT: {api_key_status}
        
        PAGE STATS:
        - Words: {data.get('word_count')}
        - Title Len: {len(data.get('title') or '')}
        - H1 Count: {len(data.get('headings', {}).get('h1', []))}
        
        ISSUES: {json.dumps(issues)}
        COMPETITORS: {json.dumps(competitors)}
        FIXES: {json.dumps(fixes)}
        """

        system_msg = """Sei un Senior SEO Auditor. Genera un report DETTAGLIATO Markdown con questa struttura:
        
        # 🚀 SEO Audit Report: [URL]
        Data: [DATA ODIERNA]
        **Stack Utilizzato:** [Tech Stack]

        ## 🧠 Executive Summary
        - **SEO Score Stimato:** **[Score]/100**
        - **Problemi individuati:** [COUNT]
        - **Fix proposti:** [COUNT]
        
        (Breve paragrafo riassuntivo)

        ---
        ## 🔒 Analisi Tecnica & Sicurezza 
        - HTTPS: [Sì/No]
        - Sicurezza API: [STATUS]
        
        ---
        ## 📊 Metriche Pagina
        | Metrica | Valore |
        | :--- | :--- |
        | Parole | [X] |
        | Lunghezza Title | [X] |
        | H1 Tags | [X] |

        ---
        ## 🚨 Problemi Rilevati
        [Lista problemi in tabella]

        ---
        ## ⚔️ Competitor Analysis
        [Lista competitor]

        ---
        ## 🛠️ Action Plan
        [Fix tecnici con codice]
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

