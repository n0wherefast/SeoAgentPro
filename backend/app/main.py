import sys
from pathlib import Path

# Fix PYTHONPATH - aggiungi backend/ al path per import assoluti
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import Response
from app.routes.scan import router as scan_router
from app.routes.autofix import router as autofix_router
from app.routes.scan_full import router as scan_full_router
from app.routes.graph_scan import router as graph_scan_router
from fastapi.middleware.cors import CORSMiddleware



env_path = backend_dir / ".env"
load_dotenv(env_path)

app = FastAPI(title="SEO Agent Pro - Backend")

# CORS middleware must be added BEFORE routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_router, prefix="/api")
# app.include_router(autofix_router, prefix="/api")
app.include_router(scan_full_router, prefix="/api")
app.include_router(graph_scan_router, prefix="/api")

# Catch-all OPTIONS for preflight CORS requests
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )