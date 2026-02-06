"""
Base Agent Pattern for SEO-PRO
All agents inherit from BaseAgent for consistency.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.core.llm_factory import get_shared_llm
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all SEO agents.
    
    Provides:
    - LLM access (singleton)
    - State management
    - Standard execution flow
    - Error handling
    - Logging
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.llm = get_shared_llm()
        self.state = {}
        self.logger = logger
    
    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze input data and return raw analysis results.
        
        Args:
            data: Input data for analysis
            
        Returns:
            Dict with analysis results
        """
        pass
    
    @abstractmethod
    def generate_recommendations(self, analysis: Dict[str, Any]) -> list:
        """
        Generate actionable recommendations based on analysis.
        
        Args:
            analysis: Results from analyze()
            
        Returns:
            List of recommendation dicts
        """
        pass
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution flow: analyze → recommendations → format.
        
        Args:
            data: Input data
            
        Returns:
            Complete agent output with analysis and recommendations
        """
        try:
            self._log("start", f"Executing {self.name}")
            
            # Phase 1: Analysis
            analysis = self.analyze(data)
            self.state["analysis"] = analysis
            self._log("analyze", "Analysis complete")
            
            # Phase 2: Recommendations
            recommendations = self.generate_recommendations(analysis)
            self.state["recommendations"] = recommendations
            self._log("recommendations", f"Generated {len(recommendations)} recommendations")
            
            # Phase 3: Format output
            output = self._format_output(analysis, recommendations)
            self._log("complete", f"{self.name} execution complete")
            
            return output
            
        except Exception as e:
            self._log("error", f"Agent execution failed: {str(e)}")
            return self._handle_error(e)
    
    def _format_output(self, analysis: Dict[str, Any], recommendations: list) -> Dict[str, Any]:
        """
        Format final output (can be overridden).
        """
        return {
            "agent": self.name,
            "analysis": analysis,
            "recommendations": recommendations,
            "status": "success"
        }
    
    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        Handle errors gracefully.
        """
        self.logger.error(f"❌ {self.name} error: {error}", exc_info=True)
        return {
            "agent": self.name,
            "status": "error",
            "error": str(error),
            "analysis": {},
            "recommendations": []
        }
    
    def _log(self, step: str, message: str):
        """
        Log agent activity.
        """
        log_entry = {
            "agent": self.name,
            "step": step,
            "message": message
        }
        self.state.setdefault("logs", []).append(log_entry)
        self.logger.info(f"[{self.name}] {step}: {message}")
