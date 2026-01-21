"""
Singleton LLM Factory Pattern
Centralizes OpenAI ChatOpenAI instance creation to reduce overhead and costs.
All modules should use get_shared_llm() instead of creating new instances.
"""

from langchain_openai import ChatOpenAI
import os
from typing import Optional

_llm_instance: Optional[ChatOpenAI] = None
_streaming_instance: Optional[ChatOpenAI] = None


def get_shared_llm(streaming: bool = False) -> ChatOpenAI:
    """
    Get the singleton ChatOpenAI LLM instance.
    
    Args:
        streaming: Whether to enable streaming mode
        
    Returns:
        ChatOpenAI instance configured from environment variables
        
    Benefits:
    - Single connection pool reused across all modules
    - Reduces API initialization overhead
    - Centralizes LLM configuration (model, temperature, API key)
    - Easy to swap model via LLM_MODEL environment variable
    """
    global _llm_instance, _streaming_instance
    
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if streaming:
        if _streaming_instance is None:
            _streaming_instance = ChatOpenAI(
                model=model_name,
                temperature=0,
                openai_api_key=api_key,
                streaming=True
            )
        return _streaming_instance
    else:
        if _llm_instance is None:
            _llm_instance = ChatOpenAI(
                model=model_name,
                temperature=0,
                openai_api_key=api_key,
                streaming=False
            )
        return _llm_instance


def reset_llm_instances():
    """
    Reset LLM instances (useful for testing or changing models at runtime).
    """
    global _llm_instance, _streaming_instance
    _llm_instance = None
    _streaming_instance = None
