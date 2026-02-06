"""
Authority Agent - Domain Authority Analysis with AI Insights
Analyzes site authority and provides competitive intelligence.
"""

from typing import Dict, Any
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate


AUTHORITY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Sei un esperto di Domain Authority, Link Building e SEO Off-Page.
    
    Analizza i dati forniti e:
    1. Spiega PERCHÉ un sito ha più/meno authority dell'altro
    2. Identifica GAP specifici (backlinks, content, social signals)
    3. Fornisci azioni CONCRETE per colmare il gap
    
    Rispondi in italiano, in modo chiaro e actionable.
    
    Formato risposta:
    
    ## 📊 Analisi Gap Authority
    [Spiegazione dettagliata del gap in 2-3 frasi]
    
    ## 🎯 Fattori Chiave
    - **Backlinks**: [analisi]
    - **Content Quality**: [analisi]
    - **Social Signals**: [analisi]
    
    ## 💡 Azioni Immediate (Priority Order)
    1. [Azione specifica con timeline]
    2. [Azione specifica con timeline]
    3. [Azione specifica con timeline]
    """),
    ("user", """
    **IL TUO SITO:**
    - Authority Score: {your_authority}
    - Backlinks Stimati: {your_backlinks}
    - Content Score: {your_content}
    - Social Presence: {your_social}
    
    **COMPETITOR:**
    - Authority Score: {comp_authority}
    - Backlinks Stimati: {comp_backlinks}
    - Content Score: {comp_content}
    - Social Presence: {comp_social}
    
    **GAP:** {gap} punti (competitor vince di {gap_percent}%)
    
    Analizza e genera raccomandazioni.
    """)
])


class AuthorityAgent(BaseAgent):
    """
    Agent for authority analysis with AI-powered competitive insights.
    
    Input:
        - your_scan: Scraped data from your site
        - competitor_scan: Scraped data from competitor (optional)
        
    Output:
        - authority_scores: Numerical scores
        - gap_analysis: AI explanation of differences
        - recommendations: Actionable steps to improve
    """
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate authority metrics using existing engine.
        """
        from app.modules.authority_engine import run_authority_engine
        
        your_scan = data.get("your_scan", {})
        competitor_scan = data.get("competitor_scan")
        
        # Use existing authority engine for calculations
        authority_data = run_authority_engine(your_scan, competitor_scan)
        
        # Enrich with additional metrics
        your_backlinks = self._estimate_backlinks(your_scan)
        your_social = self._count_social_signals(your_scan)
        your_content = self._estimate_content_score(your_scan)
        
        comp_backlinks = 0
        comp_social = 0
        comp_content = 0
        if competitor_scan:
            comp_backlinks = self._estimate_backlinks(competitor_scan)
            comp_social = self._count_social_signals(competitor_scan)
            comp_content = self._estimate_content_score(competitor_scan)
        
        authority_data["your_backlinks"] = your_backlinks
        authority_data["your_social"] = your_social
        authority_data["your_content_score"] = your_content
        authority_data["competitor_backlinks"] = comp_backlinks
        authority_data["competitor_social"] = comp_social
        authority_data["competitor_content_score"] = comp_content
        
        return authority_data
    
    def generate_recommendations(self, analysis: Dict[str, Any]) -> list:
        """
        Use LLM to generate strategic authority-building recommendations.
        """
        your_auth = analysis.get("your_authority") or 0
        comp_auth = analysis.get("competitor_authority") or 0
        
        gap = comp_auth - your_auth
        gap_percent = int((gap / max(1, comp_auth)) * 100) if comp_auth > 0 else 0
        
        # If no competitor or no gap, return default recommendations
        if gap <= 0 or comp_auth == 0:
            return self._default_recommendations(your_auth)
        
        # Prepare LLM prompt
        messages = AUTHORITY_PROMPT.format_messages(
            your_authority=your_auth,
            your_backlinks=analysis.get("your_backlinks", 0),
            your_content=analysis.get("your_content_score", 0),
            your_social=analysis.get("your_social", 0),
            comp_authority=comp_auth,
            comp_backlinks=analysis.get("competitor_backlinks", 0),
            comp_content=analysis.get("competitor_content_score", 0),
            comp_social=analysis.get("competitor_social", 0),
            gap=gap,
            gap_percent=gap_percent
        )
        
        # Get LLM insights
        result = self.llm.invoke(messages)
        
        # Parse recommendations from LLM output
        recommendations = self._parse_llm_recommendations(result.content)
        
        return recommendations
    
    def _estimate_backlinks(self, scan: Dict) -> int:
        """
        Estimate backlinks from external link count (proxy metric).
        """
        links = scan.get("links", [])
        external = sum(1 for l in links if isinstance(l, dict) and not l.get("internal", True))
        # Multiply by factor (sites with many external links tend to have backlinks)
        return external * 3
    
    def _count_social_signals(self, scan: Dict) -> int:
        """
        Count social media presence.
        """
        social_links = scan.get("social_links", [])
        return len(social_links) if isinstance(social_links, list) else 0
    
    def _estimate_content_score(self, scan: Dict) -> int:
        """
        Estimate content quality score (0-100).
        """
        paragraphs = scan.get("paragraphs", []) or []
        wordcount = sum(len(p.split()) for p in paragraphs)
        return min(100, int(wordcount / 10)) if wordcount > 0 else 0
    
    def _parse_llm_recommendations(self, llm_output: str) -> list:
        """
        Parse LLM output into structured recommendations.
        """
        recommendations = []
        lines = llm_output.split("\n")
        
        current_rec = None
        for line in lines:
            line = line.strip()
            
            # Detect numbered recommendations
            if line and (line[0].isdigit() or line.startswith("-")):
                if current_rec:
                    recommendations.append(current_rec)
                
                # Clean line
                cleaned = line.lstrip("0123456789.-) ").strip()
                current_rec = {
                    "action": cleaned,
                    "priority": len(recommendations) + 1,
                    "category": "authority"
                }
        
        # Add last recommendation
        if current_rec:
            recommendations.append(current_rec)
        
        return recommendations[:10]  # Limit to top 10
    
    def _default_recommendations(self, current_authority: int) -> list:
        """
        Fallback recommendations when no competitor data.
        """
        if current_authority >= 70:
            return [
                {"action": "Mantieni la tua authority alta con content updates regolari", "priority": 1, "category": "authority"},
                {"action": "Espandi presenza su nuove piattaforme social", "priority": 2, "category": "authority"}
            ]
        elif current_authority >= 40:
            return [
                {"action": "Crea 5 pillar content da 2000+ parole", "priority": 1, "category": "authority"},
                {"action": "Avvia campagna guest posting su siti DR 50+", "priority": 2, "category": "authority"},
                {"action": "Ottimizza link interni esistenti", "priority": 3, "category": "authority"}
            ]
        else:
            return [
                {"action": "URGENTE: Costruisci base content (10+ articoli 1000+ parole)", "priority": 1, "category": "authority"},
                {"action": "Ottieni primi 20 backlinks da directory quality", "priority": 2, "category": "authority"},
                {"action": "Setup profili social business completi", "priority": 3, "category": "authority"}
            ]
    
    def _format_output(self, analysis: Dict[str, Any], recommendations: list) -> Dict[str, Any]:
        """
        Format authority agent output.
        """
        return {
            "agent": self.name,
            "status": "success",
            "authority_scores": {
                "your_authority": analysis.get("your_authority"),
                "competitor_authority": analysis.get("competitor_authority"),
                "gap": (analysis.get("competitor_authority") or 0) - (analysis.get("your_authority") or 0)
            },
            "metrics": {
                "your_backlinks": analysis.get("your_backlinks", 0),
                "competitor_backlinks": analysis.get("competitor_backlinks", 0),
                "your_social": analysis.get("your_social", 0),
                "competitor_social": analysis.get("competitor_social", 0)
            },
            "recommendations": recommendations,
            "full_analysis": analysis
        }
