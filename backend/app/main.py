import sys
from pathlib import Path

# Fix PYTHONPATH - aggiungi backend/ al path per import assoluti
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import os
from dotenv import load_dotenv

# Load .env BEFORE any module imports so API keys are available at import time
env_path = backend_dir / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, Request
from fastapi.responses import Response
from app.routes.scan import router as scan_router
from app.routes.scan_full import router as scan_full_router
from app.routes.graph_scan import router as graph_scan_router
from app.routes.chat import router as chat_router
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

app = FastAPI(
    title="SEO Agent Pro - Backend",
    version="1.0.0",
    description="AI-powered SEO audit platform with RAG and AI Chat"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware — restrict to known frontend origins
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(scan_router, prefix="/api")
app.include_router(scan_full_router, prefix="/api")
app.include_router(graph_scan_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Index the SEO knowledge base on startup (idempotent)."""
    try:
        from app.core.knowledge_indexer import index_knowledge_base
        count = index_knowledge_base()
        import logging
        logging.getLogger(__name__).info("Knowledge base ready: %d documents", count)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Knowledge base indexing skipped: %s", e)


@app.get("/api/health")
async def health():
    """Detailed health check endpoint."""
    # Check RAG collections
    rag_status = "unknown"
    try:
        from app.core.vector_store import get_chroma_client
        client = get_chroma_client()
        collections = [c.name for c in client.list_collections()]
        rag_status = f"ok ({len(collections)} collections)"
    except Exception:
        rag_status = "unavailable"
    
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "tavily_configured": bool(os.getenv("TAVILY_API_KEY")),
        "rag_status": rag_status,
    }

# Catch-all OPTIONS for preflight CORS requests
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origins.split(",")[0].strip(),
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )