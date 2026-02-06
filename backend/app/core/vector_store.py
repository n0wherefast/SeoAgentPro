"""
Singleton Vector Store Manager
Manages ChromaDB persistent client and OpenAI embeddings.
All modules should use get_vector_store() / get_embeddings() instead of creating new instances.
"""

import os
import logging
from typing import Optional
from pathlib import Path

import chromadb
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.ClientAPI] = None
_embeddings_instance: Optional[OpenAIEmbeddings] = None

# Persistent storage directory (relative to backend/)
CHROMA_PERSIST_DIR = str(Path(__file__).resolve().parent.parent.parent / "chroma_data")


def get_chroma_client() -> chromadb.ClientAPI:
    """
    Get the singleton persistent ChromaDB client.
    Data is stored in backend/chroma_data/ for persistence across restarts.
    """
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        logger.info("ChromaDB persistent client initialized at %s", CHROMA_PERSIST_DIR)
    return _chroma_client


def get_embeddings() -> OpenAIEmbeddings:
    """
    Get the singleton OpenAI Embeddings instance.
    Uses text-embedding-3-small for best cost/performance balance.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        _embeddings_instance = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key,
        )
        logger.info("OpenAI Embeddings initialized with model=%s", model)
    return _embeddings_instance


def get_collection(name: str) -> chromadb.Collection:
    """
    Get or create a named ChromaDB collection.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def reset_vector_store():
    """Reset all singleton instances (for testing)."""
    global _chroma_client, _embeddings_instance
    _chroma_client = None
    _embeddings_instance = None
