"""
Multi-Provider LLM Factory Pattern
Centralizes LLM instance creation for multiple providers (OpenAI, Anthropic, Llama, Devstral/Mistral).
All modules should use get_shared_llm() instead of creating new instances.

Supported providers:
  - openai    → ChatOpenAI (GPT-4o, GPT-4o-mini, GPT-4-turbo, o3-mini, …)
  - anthropic → ChatAnthropic (Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3 Haiku, …)
  - mistral   → ChatMistralAI (Devstral, Mistral Large, Codestral, …)
  - ollama    → ChatOllama (Llama 3.3, Llama 3.1, Qwen, Gemma, any local model via Ollama)
  - lmstudio  → ChatOpenAI (any local model via LM Studio — OpenAI-compatible API)
"""

import os
import logging
from typing import Optional, Dict, Any
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

# ── Provider → Model defaults ──────────────────────────────────────────────
PROVIDER_DEFAULTS: Dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    # "mistral": "devstral-small-2505",
    "ollama": "llama3.1:8b",
    # "lmstudio": "mistralai/devstral-small-2-2512",
}

PROVIDER_MODELS: Dict[str, list] = {
    "openai": [
        "gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o3-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022",
        "claude-3-haiku-20240307", "claude-3-opus-20240229",
    ],
    # "mistral": [
    #     "devstral-small-2505", "mistral-large-latest",
    #     "codestral-latest", "mistral-small-latest",
    # ],
    "ollama": [
        "llama3.1:8b", "llama3.3:latest", "llama3.1:70b",
        "qwen2.5:latest", "gemma2:latest", "deepseek-r1:latest",
    ],
    # "lmstudio": [
    #     "mistralai/devstral-small-2-2512",
    #     "meta-llama/llama-3.1-8b",
    #     "qwen/qwen2.5-7b",
    # ],
}

# ── Singleton cache ─────────────────────────────────────────────────────────
_instances: Dict[str, BaseChatModel] = {}


def _resolve_provider() -> str:
    """Return the active provider name from LLM_PROVIDER env var."""
    return os.getenv("LLM_PROVIDER", "openai").lower().strip()


def _resolve_model(provider: str) -> str:
    """Return the active model name from LLM_MODEL env var or provider default."""
    explicit = os.getenv("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    return PROVIDER_DEFAULTS.get(provider, "gpt-4o-mini")


def _build_llm(provider: str, model: str, streaming: bool) -> BaseChatModel:
    """Instantiate the correct LangChain chat model for the given provider."""
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            streaming=streaming,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            streaming=streaming,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )

    elif provider == "mistral":
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=model,
            temperature=temperature,
            mistral_api_key=os.getenv("MISTRAL_API_KEY"),
            streaming=streaming,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
            streaming=streaming,
        )

    elif provider == "lmstudio":
        # LM Studio uses OpenAI-compatible API on localhost:1234
        from langchain_openai import ChatOpenAI
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=base_url,
            api_key="lm-studio",  # LM Studio doesn't require real API key
            streaming=streaming,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: {', '.join(PROVIDER_DEFAULTS.keys())}"
        )


def get_shared_llm(streaming: bool = False) -> BaseChatModel:
    """
    Get the singleton LLM instance for the active provider.

    Args:
        streaming: Whether to enable streaming mode

    Returns:
        BaseChatModel instance (ChatOpenAI, ChatAnthropic, ChatMistralAI, or ChatOllama)

    The provider/model are determined from environment variables:
        LLM_PROVIDER  – openai | anthropic | mistral | ollama | lmstudio  (default: openai)
        LLM_MODEL     – model name (auto-detected per provider if omitted)
    """
    provider = _resolve_provider()
    model = _resolve_model(provider)
    cache_key = f"{provider}:{model}:stream={streaming}"

    if cache_key not in _instances:
        logger.info("Creating LLM instance: provider=%s model=%s streaming=%s", provider, model, streaming)
        _instances[cache_key] = _build_llm(provider, model, streaming)

    return _instances[cache_key]


def set_provider(provider: str, model: Optional[str] = None) -> Dict[str, str]:
    """
    Switch LLM provider and model at runtime. Clears cached instances.

    Args:
        provider: Provider name (openai, anthropic, mistral, ollama)
        model: Optional model name; uses provider default if omitted

    Returns:
        Dict with active provider and model
    """
    provider = provider.lower().strip()
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError(f"Unsupported provider: '{provider}'. Supported: {', '.join(PROVIDER_DEFAULTS.keys())}")

    os.environ["LLM_PROVIDER"] = provider
    if model:
        os.environ["LLM_MODEL"] = model
    else:
        # Clear LLM_MODEL so the provider default is used
        os.environ.pop("LLM_MODEL", None)

    reset_llm_instances()

    active_model = _resolve_model(provider)
    logger.info("Switched LLM to provider=%s model=%s", provider, active_model)
    return {"provider": provider, "model": active_model}


def get_current_provider_info() -> Dict[str, Any]:
    """Return current provider, model, and available options."""
    provider = _resolve_provider()
    model = _resolve_model(provider)
    return {
        "current_provider": provider,
        "current_model": model,
        "providers": {
            name: {
                "models": models,
                "default_model": PROVIDER_DEFAULTS[name],
                "configured": _is_provider_configured(name),
            }
            for name, models in PROVIDER_MODELS.items()
        },
    }


def _is_provider_configured(provider: str) -> bool:
    """Check if the required API key / service is available for a provider."""
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    elif provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    elif provider == "mistral":
        return bool(os.getenv("MISTRAL_API_KEY"))
    elif provider == "ollama":
        # Ollama is local — always "configured" if env allows it
        return True
    elif provider == "lmstudio":
        # LM Studio is local — always "configured" if running
        return True
    return False


def reset_llm_instances():
    """
    Reset all cached LLM instances (useful for testing or changing models at runtime).
    """
    global _instances
    _instances.clear()
