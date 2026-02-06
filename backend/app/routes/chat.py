"""
Chat API Route
POST /api/chat — SSE streaming chat endpoint with RAG context.
POST /api/chat/clear — Clear conversation history.
GET /api/chat/history — Get conversation history.
GET /api/chat/scans — List recent scans for context selection.
POST /api/chat/upload-pdf — Upload PDF report for RAG indexing.
"""

import json
import logging
import hashlib
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.modules.chat_agent import chat_stream, get_conversation_history, clear_conversation

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"
    scan_id: Optional[str] = None
    domain: Optional[str] = None


class ClearRequest(BaseModel):
    conversation_id: str = "default"


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint with RAG-augmented responses.
    Returns SSE stream of tokens.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if len(req.message) > 5000:
        raise HTTPException(status_code=400, detail="Message too long (max 5000 chars)")
    
    async def event_generator():
        try:
            async for token in chat_stream(
                message=req.message.strip(),
                conversation_id=req.conversation_id,
                scan_id=req.scan_id,
                domain=req.domain,
            ):
                # SSE format: each token as a data event
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            
            # Signal completion
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True)
            error_payload = json.dumps({"error": str(e)[:200]}, ensure_ascii=False)
            yield f"data: {error_payload}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def get_history(conversation_id: str = "default"):
    """Get the conversation history for a conversation."""
    history = get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": history}


@router.post("/chat/clear")
async def clear_history(req: ClearRequest):
    """Clear the conversation history."""
    clear_conversation(req.conversation_id)
    return {"status": "cleared", "conversation_id": req.conversation_id}


@router.get("/chat/scans")
async def list_recent_scans(limit: int = 20):
    """
    List recent scans stored in RAG for chat context selection.
    Returns unique scans with scan_id, domain, url, date, score.
    """
    try:
        from app.core.vector_store import get_collection
        collection = get_collection("scan_results")
        if collection.count() == 0:
            return {"scans": []}

        results = collection.get(
            where={"section": "overview"},
            include=["metadatas"],
            limit=limit,
        )

        scans = []
        seen = set()
        for meta in (results.get("metadatas") or []):
            sid = meta.get("scan_id", "")
            if sid and sid not in seen:
                seen.add(sid)
                scans.append({
                    "scan_id": sid,
                    "domain": meta.get("domain", ""),
                    "url": meta.get("url", ""),
                    "scan_date": meta.get("scan_date", ""),
                    "seo_score": meta.get("seo_score", 0),
                    "tech_stack": meta.get("tech_stack", ""),
                })

        # Sort by date descending
        scans.sort(key=lambda s: s["scan_date"], reverse=True)
        return {"scans": scans[:limit]}
    except Exception as e:
        logger.error("list_recent_scans failed: %s", e)
        return {"scans": []}


# =========================
# PDF UPLOAD for RAG
# =========================

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_PDF_PAGES = 200


def _extract_pdf_text(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from PDF using PyMuPDF. Returns (text, num_pages)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = min(len(doc), MAX_PDF_PAGES)
    text_parts = []
    for i in range(pages):
        page = doc.load_page(i)
        text_parts.append(page.get_text())
    doc.close()
    return "\n\n".join(text_parts), pages


def _chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


@router.post("/chat/upload-pdf")
async def upload_pdf_for_rag(
    file: UploadFile = File(...),
    label: str = Form(""),
):
    """
    Upload a PDF report and index it into ChromaDB for RAG retrieval.
    The AI Chat will then be able to answer questions about this PDF.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo file PDF accettati.")

    content = await file.read()
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File troppo grande (max {MAX_PDF_SIZE // (1024*1024)} MB).",
        )
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File PDF vuoto o corrotto.")

    try:
        text, num_pages = _extract_pdf_text(content)
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Impossibile leggere il PDF: {str(e)[:200]}")

    if not text or len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Il PDF non contiene testo estraibile.")

    chunks = _chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Nessun contenuto utile estratto dal PDF.")

    try:
        from app.core.vector_store import get_collection, get_embeddings

        collection = get_collection("uploaded_documents")
        embeddings = get_embeddings()

        doc_id = hashlib.md5(content[:1000]).hexdigest()[:16]
        doc_label = label.strip() or file.filename or "report.pdf"
        upload_date = datetime.now(timezone.utc).isoformat()

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": file.filename or "unknown.pdf",
                "label": doc_label,
                "upload_date": upload_date,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "num_pages": num_pages,
                "source": "pdf_upload",
            }
            for i in range(len(chunks))
        ]

        vectors = embeddings.embed_documents(chunks)
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=vectors,
        )

        logger.info(
            "✅ PDF indexed: %s (%d pages, %d chunks, doc_id=%s)",
            file.filename, num_pages, len(chunks), doc_id,
        )
        return {
            "status": "ok",
            "doc_id": doc_id,
            "filename": file.filename,
            "label": doc_label,
            "pages": num_pages,
            "chunks": len(chunks),
            "characters": len(text),
        }
    except Exception as e:
        logger.error("PDF indexing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Errore indicizzazione: {str(e)[:200]}")


@router.get("/chat/documents")
async def list_uploaded_documents():
    """List all uploaded PDF documents."""
    try:
        from app.core.vector_store import get_collection

        collection = get_collection("uploaded_documents")
        if collection.count() == 0:
            return {"documents": []}

        results = collection.get(
            where={"chunk_index": 0},
            include=["metadatas"],
            limit=50,
        )

        docs = []
        seen = set()
        for meta in (results.get("metadatas") or []):
            did = meta.get("doc_id", "")
            if did and did not in seen:
                seen.add(did)
                docs.append({
                    "doc_id": did,
                    "filename": meta.get("filename", ""),
                    "label": meta.get("label", ""),
                    "upload_date": meta.get("upload_date", ""),
                    "pages": meta.get("num_pages", 0),
                    "chunks": meta.get("total_chunks", 0),
                })

        docs.sort(key=lambda d: d["upload_date"], reverse=True)
        return {"documents": docs}
    except Exception as e:
        logger.error("list_uploaded_documents failed: %s", e)
        return {"documents": []}
