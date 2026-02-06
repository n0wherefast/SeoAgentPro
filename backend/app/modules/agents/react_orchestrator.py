"""
ReAct Autonomous Orchestrator for SEO-PRO
Uses Reasoning + Action loop with circuit breaker.
"""

from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_factory import get_shared_llm
import json
import logging

logger = logging.getLogger(__name__)


class ReActOrchestrator:
    """
    Autonomous agent using ReAct (Reasoning + Acting) pattern.
    
    Features:
    - Self-directed tool selection
    - Adaptive workflow based on intermediate results
    - Circuit breaker (max_iterations) to prevent infinite loops
    - Detailed reasoning logs for debugging
    """
    
    # Tool registry with descriptions
    AVAILABLE_TOOLS = {
        "scrape_url": {
            "description": "Extract SEO data from URL (title, meta, headings, content, images)",
            "cost": "low",
            "avg_time": "2s"
        },
        "detect_seo_issues": {
            "description": "Analyze scraped data for 22 on-page SEO issues (title, meta, headings, etc.)",
            "cost": "low",
            "avg_time": "0.5s"
        },
        "run_technical_checks": {
            "description": "Deep technical analysis (robots.txt, sitemap, canonicals, SSL, redirects)",
            "cost": "medium",
            "avg_time": "3s"
        },
        "analyze_performance": {
            "description": "Lighthouse performance audit (Core Web Vitals, LCP, FID, CLS)",
            "cost": "high",
            "avg_time": "8s"
        },
        "analyze_competitors": {
            "description": "Compare with competitor URL (keywords, content gap, authority comparison)",
            "cost": "high",
            "avg_time": "10s"
        },
        "find_top_competitors": {
            "description": "Automatically discover top 3 competitors for the URL (uses search engine data)",
            "cost": "very_high",
            "avg_time": "15s"
        },
        "analyze_authority": {
            "description": "Domain authority analysis with AI-powered competitive insights",
            "cost": "medium",
            "avg_time": "4s"
        },
        "optimize_keywords": {
            "description": "Keyword presence analysis and AI placement recommendations",
            "cost": "medium",
            "avg_time": "3s"
        },
        "generate_fixes": {
            "description": "Generate actionable code fixes for detected SEO issues",
            "cost": "medium",
            "avg_time": "2s"
        },
        "create_seo_strategy": {
            "description": "Generate comprehensive SEO strategy based on all findings",
            "cost": "high",
            "avg_time": "5s"
        },
        "create_roadmap": {
            "description": "Create prioritized 30/60/90 day SEO roadmap",
            "cost": "high",
            "avg_time": "4s"
        },
        "calculate_score": {
            "description": "Calculate overall SEO score (0-100) based on all factors",
            "cost": "low",
            "avg_time": "0.5s"
        }
    }
    
    # ReAct prompt for reasoning
    REACT_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert SEO analyst agent with autonomous decision-making capabilities.

Your goal: Perform the most effective SEO analysis for the given URL within {max_iterations} iterations.

Available tools:
{tools_list}

Current state:
- URL: {url}
- Iteration: {current_iteration}/{max_iterations}
- Completed actions: {completed_actions}
- Current findings: {current_findings}

Instructions:
1. THINK: Analyze current findings and decide next best action
2. REASON: Explain why this action is valuable now
3. ACT: Choose ONE tool to execute
4. EVALUATE: After action, decide if you have enough information or need more

Optimization rules:
- Start with low-cost essentials (scrape_url, detect_seo_issues)
- Skip tools if findings show they're unnecessary (e.g., skip performance if site is fast)
- Prioritize high-impact discoveries
- Stop early if you have sufficient actionable insights
- Use expensive tools (competitors, performance) only if critical issues detected

Output format (JSON):
{{
  "reasoning": "Why I'm choosing this action based on current findings",
  "next_action": "tool_name",
  "expected_value": "What insight this will provide",
  "stop_after": true/false,
  "confidence": 0-100
}}

If you believe you have enough information to provide valuable recommendations, set "next_action": "STOP" and "stop_after": true.
"""),
        ("user", "Decide the next action for SEO analysis of {url}")
    ])
    
    def __init__(self, max_iterations: int = 8):
        """
        Initialize ReAct orchestrator.
        
        Args:
            max_iterations: Maximum number of tool executions (circuit breaker)
        """
        self.max_iterations = max_iterations
        self.llm = get_shared_llm()
        self.state = {}
        self.reasoning_log = []
        
    def execute(self, url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute autonomous SEO analysis with ReAct loop.
        
        Args:
            url: Target URL
            options: Optional parameters (keywords, competitor_url, etc.)
            
        Returns:
            Complete analysis results with reasoning log
        """
        options = options or {}
        
        # Initialize state
        self.state = {
            "url": url,
            "options": options,
            "completed_actions": [],
            "findings": {},
            "iteration": 0,
            "total_cost_estimate": 0
        }
        
        logger.info(f"Starting autonomous analysis for {url} (max {self.max_iterations} iterations)")
        
        # ReAct loop
        while self.state["iteration"] < self.max_iterations:
            self.state["iteration"] += 1
            
            # Get next action from LLM
            decision = self._reason_next_action()
            
            if not decision or decision.get("next_action") == "STOP":
                logger.info(f"Agent decided to stop at iteration {self.state['iteration']}")
                break
            
            # Execute action
            self._execute_action(decision)
            
            # Check if agent wants to stop
            if decision.get("stop_after"):
                logger.info("Agent set stop_after=true, terminating loop")
                break
        
        # Final compilation
        return self._compile_final_report()
    
    def execute_stream(self, url: str, options: Dict[str, Any] = None):
        """
        Execute autonomous SEO analysis with real-time streaming.
        Yields SSE events as analysis progresses.
        """
        options = options or {}
        
        def sse(event: str, data: dict):
            import json
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"
        
        # Initialize state
        self.state = {
            "url": url,
            "options": options,
            "completed_actions": [],
            "findings": {},
            "iteration": 0,
            "total_cost_estimate": 0
        }
        
        logger.info(f"Starting autonomous streaming analysis for {url} (max {self.max_iterations} iterations)")
        yield sse("log", {"message": f"🤖 Starting autonomous analysis (max {self.max_iterations} iterations)", "step": "init", "status": "running"})
        
        # ReAct loop with streaming
        while self.state["iteration"] < self.max_iterations:
            self.state["iteration"] += 1
            
            # Get next action from LLM
            yield sse("log", {"message": f"🧠 AI thinking... (iteration {self.state['iteration']})", "step": "reasoning", "status": "running"})
            decision = self._reason_next_action()
            
            if not decision or decision.get("next_action") == "STOP":
                logger.info(f"Agent decided to stop at iteration {self.state['iteration']}")
                yield sse("log", {"message": "✅ Agent decided analysis is complete", "step": "reasoning", "status": "done"})
                break
            
            # Stream reasoning
            yield sse("reasoning", {
                "iteration": self.state["iteration"],
                "reasoning": decision.get("reasoning"),
                "action": decision.get("next_action"),
                "confidence": decision.get("confidence", 85)
            })
            
            # Execute action with streaming
            action = decision.get("next_action")
            yield sse("log", {"message": f"⚙️ Executing: {action}", "step": action, "status": "running"})
            
            self._execute_action(decision)
            
            # Stream intermediate results based on action
            if action in self.state["findings"]:
                result = self.state["findings"][action]
                
                # Emit specific events based on tool
                if action == "scrape_url":
                    yield sse("scrape", result)
                elif action == "detect_seo_issues":
                    yield sse("onpage_errors", result.get("issues", []))
                elif action == "calculate_score":
                    yield sse("seo_score", {"score": result.get("score", 0)})
                elif action == "run_technical_checks":
                    yield sse("technical", result)
                elif action == "analyze_performance":
                    yield sse("performance", result)
                elif action == "generate_fixes":
                    yield sse("fixes", result.get("fixes", []))
            
            yield sse("log", {"message": f"✓ {action} complete", "step": action, "status": "done"})
            
            # Check if agent wants to stop
            if decision.get("stop_after"):
                logger.info("Agent set stop_after=true, terminating loop")
                yield sse("log", {"message": "✅ Agent reached stopping criteria", "step": "reasoning", "status": "done"})
                break
        
        # Final compilation
        yield sse("log", {"message": "📊 Compiling final report...", "step": "compile", "status": "running"})
        final_result = self._compile_final_report()
        
        yield sse("done", final_result)
    
    def _reason_next_action(self) -> Optional[Dict[str, Any]]:
        """
        Use LLM to decide next action based on current state.
        """
        try:
            # Format tools list
            tools_list = "\n".join([
                f"- {name}: {info['description']} (cost: {info['cost']}, ~{info['avg_time']})"
                for name, info in self.AVAILABLE_TOOLS.items()
            ])
            
            # Format current findings summary
            findings_summary = self._summarize_findings()
            
            # Invoke LLM
            messages = self.REACT_PROMPT.format_messages(
                url=self.state["url"],
                max_iterations=self.max_iterations,
                current_iteration=self.state["iteration"],
                tools_list=tools_list,
                completed_actions=", ".join(self.state["completed_actions"]) or "None",
                current_findings=findings_summary
            )
            
            response = self.llm.invoke(messages)
            
            # Parse decision
            decision = self._parse_decision(response.content)
            
            # Log reasoning
            self.reasoning_log.append({
                "iteration": self.state["iteration"],
                "reasoning": decision.get("reasoning"),
                "action": decision.get("next_action"),
                "confidence": decision.get("confidence")
            })
            
            logger.info(f"Iteration {self.state['iteration']}: {decision.get('next_action')} - {decision.get('reasoning')}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in reasoning: {e}")
            return None
    
    def _parse_decision(self, content: str) -> Dict[str, Any]:
        """Parse LLM decision from JSON response."""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(content)
            return decision
        except Exception as e:
            logger.error(f"Failed to parse decision: {e}")
            # Fallback: try to extract action from text
            return {"next_action": "STOP", "reasoning": "Parse error", "stop_after": True}
    
    def _execute_action(self, decision: Dict[str, Any]):
        """Execute the chosen tool action."""
        action = decision.get("next_action")
        
        if action in self.AVAILABLE_TOOLS:
            logger.info(f"Executing: {action}")
            
            try:
                # Execute tool
                result = self._run_tool(action)
                
                # Update state
                self.state["completed_actions"].append(action)
                self.state["findings"][action] = result
                
                # Update cost estimate
                cost_map = {"low": 1, "medium": 2, "high": 4, "very_high": 8}
                self.state["total_cost_estimate"] += cost_map.get(
                    self.AVAILABLE_TOOLS[action]["cost"], 2
                )
                
            except Exception as e:
                logger.error(f"Error executing {action}: {e}")
                self.state["findings"][action] = {"error": str(e)}
    
    def _run_tool(self, tool_name: str) -> Dict[str, Any]:
        """Execute a specific SEO tool."""
        url = self.state["url"]
        options = self.state["options"]
        
        if tool_name == "scrape_url":
            from app.modules.scraper import smart_scrape_url
            return smart_scrape_url(url)
        
        elif tool_name == "detect_seo_issues":
            from app.modules.seo_detection_unified import detect_seo_issues_unified
            scraped = self.state["findings"].get("scrape_url", {})
            return {"issues": detect_seo_issues_unified(scraped)}
        
        elif tool_name == "run_technical_checks":
            from app.modules.seo_technical import run_technical_checks
            scraped = self.state["findings"].get("scrape_url", {})
            return run_technical_checks(scraped, url)
        
        elif tool_name == "analyze_performance":
            from app.modules.competitor.lighthouse_client import run_performance_engine
            return run_performance_engine(url)
        
        elif tool_name == "analyze_competitors":
            from app.modules.competitor import run_competitor_analysis
            competitor_url = options.get("competitor_url")
            if not competitor_url:
                return {"error": "No competitor_url provided"}
            scraped = self.state["findings"].get("scrape_url", {})
            return run_competitor_analysis(scraped, url, competitor_url)
        
        elif tool_name == "find_top_competitors":
            from app.modules.competitor import discover_competitors_auto
            return discover_competitors_auto(url)
        
        elif tool_name == "analyze_authority":
            from app.modules.agents.authority_agent import AuthorityAgent
            agent = AuthorityAgent()
            scraped = self.state["findings"].get("scrape_url", {})
            return agent.execute({"url": url, "scraped_data": scraped})
        
        elif tool_name == "optimize_keywords":
            from app.modules.agents.keyword_agent import KeywordAgent
            agent = KeywordAgent()
            scraped = self.state["findings"].get("scrape_url", {})
            keywords = options.get("keywords") or options.get("target_keywords", [])
            return agent.execute({"scraped_data": scraped, "target_keywords": keywords})
        
        elif tool_name == "generate_fixes":
            from app.modules.ai_fix_agents import generate_fix_suggestions
            issues = self.state["findings"].get("detect_seo_issues", {}).get("issues", [])
            scraped = self.state["findings"].get("scrape_url", {})
            return {"fixes": generate_fix_suggestions(issues, scraped)}
        
        elif tool_name == "create_seo_strategy":
            from app.modules.ai_strategy_agent import generate_seo_strategy_comprehensive
            return generate_seo_strategy_comprehensive(
                self.state["findings"].get("scrape_url", {}),
                self.state["findings"].get("detect_seo_issues", {}).get("issues", []),
                url
            )
        
        elif tool_name == "create_roadmap":
            from app.modules.ai_roadmap_agent import generate_seo_roadmap
            return generate_seo_roadmap(
                self.state["findings"].get("detect_seo_issues", {}).get("issues", []),
                self.state["findings"]
            )
        
        elif tool_name == "calculate_score":
            from app.modules.seo_rules import calculate_seo_score
            issues = self.state["findings"].get("detect_seo_issues", {}).get("issues", [])
            return {"score": calculate_seo_score(issues)}
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def _summarize_findings(self) -> str:
        """Create concise summary of current findings for LLM context."""
        if not self.state["findings"]:
            return "No findings yet"
        
        summary_parts = []
        
        # Scrape results
        if "scrape_url" in self.state["findings"]:
            scraped = self.state["findings"]["scrape_url"]
            summary_parts.append(f"Page title: {scraped.get('title', 'N/A')[:50]}")
        
        # Issues detected
        if "detect_seo_issues" in self.state["findings"]:
            issues = self.state["findings"]["detect_seo_issues"].get("issues", [])
            critical = [i for i in issues if i.get("severity") == "critical"]
            summary_parts.append(f"SEO issues: {len(issues)} total, {len(critical)} critical")
        
        # Technical status
        if "run_technical_checks" in self.state["findings"]:
            tech = self.state["findings"]["run_technical_checks"]
            errors = tech.get("technical_errors", [])
            summary_parts.append(f"Technical: {len(errors)} errors found")
        
        # Performance
        if "analyze_performance" in self.state["findings"]:
            perf = self.state["findings"]["analyze_performance"]
            score = perf.get("performance_score", "N/A")
            summary_parts.append(f"Performance score: {score}")
        
        # Score
        if "calculate_score" in self.state["findings"]:
            score = self.state["findings"]["calculate_score"].get("score", 0)
            summary_parts.append(f"SEO Score: {score}/100")
        
        return " | ".join(summary_parts) if summary_parts else "Analysis in progress"
    
    def _compile_final_report(self) -> Dict[str, Any]:
        """Compile all findings into final report."""
        # Extract data in format compatible with frontend
        seo_data = self.state["findings"].get("scrape_url", {})
        issues_result = self.state["findings"].get("detect_seo_issues", {})
        issues = issues_result.get("issues", []) if isinstance(issues_result, dict) else []
        seo_score = self.state["findings"].get("calculate_score", {}).get("score", 0)
        fixes = self.state["findings"].get("generate_fixes", {}).get("fixes", [])
        
        return {
            "url": self.state["url"],
            "mode": "autonomous",
            "iterations_used": self.state["iteration"],
            "max_iterations": self.max_iterations,
            "tools_executed": self.state["completed_actions"],
            "cost_estimate": self.state["total_cost_estimate"],
            
            # Frontend-compatible format
            "seo_data": seo_data,
            "issues": issues,
            "seo_score": seo_score,
            "fixes": fixes,
            
            # Autonomous-specific data
            "findings": self.state["findings"],
            "reasoning_log": self.reasoning_log,
            "summary": self._summarize_findings()
        }
