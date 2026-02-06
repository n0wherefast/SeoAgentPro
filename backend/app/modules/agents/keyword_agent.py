"""
Keyword Agent - Keyword Analysis & Optimization with AI
Analyzes keyword presence and provides strategic placement recommendations.
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate
import re


KEYWORD_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Sei un SEO Keyword Strategist esperto.
    
    Analizza la presenza delle keyword target e fornisci:
    1. Valutazione dell'ottimizzazione attuale (0-100)
    2. Identificazione gap keyword (dove mancano)
    3. Suggerimenti PRECISI su dove inserirle
    
    Rispondi in italiano, in modo specifico e actionable.
    
    Formato:
    
    ## 📊 Stato Attuale Keywords
    [Riepilogo: X/Y keywords ben posizionate]
    
    ## ⚠️ Gap Rilevati
    - [keyword]: manca in [posizioni]
    - [keyword]: presente ma poco enfatizzata
    
    ## 🎯 Azioni Specifiche
    1. **[Keyword]**: Inserisci in [dove] → [esempio concreto]
    2. **[Keyword]**: Modifica [cosa] → [esempio concreto]
    """),
    ("user", """
    **KEYWORD TARGET:**
    {target_keywords}
    
    **ANALISI PRESENZA:**
    {keyword_presence}
    
    **CONTENUTO ATTUALE:**
    - Title: {title}
    - Meta Description: {meta_desc}
    - H1: {h1}
    - Content Length: {content_length} parole
    
    Genera raccomandazioni per ottimizzare keyword placement.
    """)
])


class KeywordAgent(BaseAgent):
    """
    Agent for keyword analysis and strategic placement optimization.
    
    Input:
        - scraped_data: Site content
        - target_keywords: List of keywords to analyze
        
    Output:
        - keyword_analysis: Presence and optimization scores
        - recommendations: Where and how to place keywords
    """
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze keyword presence in content.
        """
        scraped = data.get("scraped_data", {})
        keywords = data.get("target_keywords", [])
        
        if not keywords:
            return {"error": "No keywords provided", "keyword_analysis": []}
        
        # Perform keyword presence analysis
        analysis = self._analyze_keyword_presence(scraped, keywords)
        
        return {
            "keywords_analyzed": len(keywords),
            "keywords_found": analysis["keywords_found"],
            "coverage_percent": analysis["coverage_percent"],
            "keyword_details": analysis["keywords"],
            "scraped_summary": {
                "title": scraped.get("title", ""),
                "meta_description": scraped.get("meta_description", ""),
                "h1": scraped.get("h1", [""])[0] if scraped.get("h1") else "",
                "content_length": sum(len(p.split()) for p in scraped.get("paragraphs", []))
            }
        }
    
    def generate_recommendations(self, analysis: Dict[str, Any]) -> list:
        """
        Use LLM to generate keyword placement recommendations.
        """
        if analysis.get("error"):
            return []
        
        # Prepare keyword presence summary
        kw_details = analysis.get("keyword_details", [])
        target_kw_str = ", ".join([k["keyword"] for k in kw_details])
        
        presence_summary = "\n".join([
            f"- {k['keyword']}: in_title={k['in_title']}, in_h1={k['in_h1']}, "
            f"in_content={k['in_content']}, score={k['optimization_score']}/100"
            for k in kw_details
        ])
        
        summary = analysis.get("scraped_summary", {})
        
        # Generate LLM recommendations
        messages = KEYWORD_PROMPT.format_messages(
            target_keywords=target_kw_str,
            keyword_presence=presence_summary,
            title=summary.get("title", ""),
            meta_desc=summary.get("meta_description", ""),
            h1=summary.get("h1", ""),
            content_length=summary.get("content_length", 0)
        )
        
        result = self.llm.invoke(messages)
        
        # Parse recommendations
        recommendations = self._parse_keyword_recommendations(result.content, kw_details)
        
        return recommendations
    
    def _analyze_keyword_presence(self, scraped: Dict, keywords: List[str]) -> Dict:
        """
        Analyze where each keyword appears in content.
        """
        title = (scraped.get("title") or "").lower()
        meta_desc = (scraped.get("meta_description") or "").lower()
        h1_list = [h.lower() for h in (scraped.get("h1") or [])]
        h2_list = [h.lower() for h in (scraped.get("h2") or [])]
        paragraphs = " ".join(scraped.get("paragraphs") or []).lower()
        alt_texts = " ".join(scraped.get("images_alt") or []).lower()
        url = (scraped.get("url") or "").lower()
        
        results = []
        total_found = 0
        
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if not kw_lower:
                continue
            
            presence = {
                "keyword": kw,
                "in_title": kw_lower in title,
                "in_meta_description": kw_lower in meta_desc,
                "in_h1": any(kw_lower in h for h in h1_list),
                "in_h2": any(kw_lower in h for h in h2_list),
                "in_content": kw_lower in paragraphs,
                "in_url": kw_lower in url,
                "in_alt_text": kw_lower in alt_texts,
                "content_count": len(re.findall(re.escape(kw_lower), paragraphs))
            }
            
            # Calculate optimization score (0-100)
            score = 0
            if presence["in_title"]: score += 25
            if presence["in_meta_description"]: score += 20
            if presence["in_h1"]: score += 20
            if presence["in_h2"]: score += 10
            if presence["in_content"]: score += 15
            if presence["in_url"]: score += 5
            if presence["in_alt_text"]: score += 5
            
            presence["optimization_score"] = min(score, 100)
            presence["status"] = "optimized" if score >= 60 else "needs_work" if score >= 30 else "missing"
            
            if score > 0:
                total_found += 1
            
            results.append(presence)
        
        return {
            "keywords": results,
            "total_keywords": len(keywords),
            "keywords_found": total_found,
            "coverage_percent": round(total_found / len(keywords) * 100) if keywords else 0,
            "summary": f"{total_found}/{len(keywords)} keywords trovate nel contenuto"
        }
    
    def _parse_keyword_recommendations(self, llm_output: str, kw_details: List[Dict]) -> list:
        """
        Parse LLM output into structured keyword recommendations.
        """
        recommendations = []
        lines = llm_output.split("\n")
        
        for line in lines:
            line = line.strip()
            
            # Detect recommendations (numbered or with keyword mentioned)
            if any(kw["keyword"].lower() in line.lower() for kw in kw_details):
                # Extract keyword from line
                matched_kw = next(
                    (kw["keyword"] for kw in kw_details if kw["keyword"].lower() in line.lower()),
                    None
                )
                
                if matched_kw and len(line) > 20:  # Valid recommendation
                    recommendations.append({
                        "keyword": matched_kw,
                        "action": line.lstrip("0123456789.-*• ").strip(),
                        "priority": len(recommendations) + 1,
                        "category": "keyword"
                    })
        
        return recommendations[:15]  # Limit to 15 recommendations
