"""
AI Chat Agent with RAG
Multi-collection retrieval (SEO knowledge + scan history) with conversation memory.
Supports streaming responses for real-time chat experience.
"""

import json
import logging
from typing import Optional, AsyncGenerator
from collections import defaultdict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.core.llm_factory import get_shared_llm
from app.core.knowledge_indexer import query_knowledge
from app.modules.scan_store import query_scan_history, get_latest_scan_id

logger = logging.getLogger(__name__)

# In-memory conversation store (keyed by conversation_id)
# In production, replace with Redis or a database
_conversations: dict[str, list] = defaultdict(list)
MAX_HISTORY = 20  # Keep last 20 messages per conversation


CHAT_SYSTEM_PROMPT = """Sei un assistente SEO esperto integrato in SEO Agent Pro.
Il tuo ruolo è ESCLUSIVAMENTE aiutare gli utenti a comprendere e migliorare il SEO dei loro siti web.

CAPACITA:
- Rispondere a domande su SEO, technical SEO, contenuti, performance e sicurezza web
- Analizzare i risultati delle scansioni SEO effettuate sulla piattaforma
- Suggerire fix specifici basati sullo stack tecnologico del sito
- Spiegare concetti SEO in modo chiaro e pratico
- Fornire codice pronto da implementare quando richiesto
- Analizzare documenti PDF caricati dall'utente relativi a SEO e web

LIMITI RIGOROSI:
- Rispondi SOLO a domande relative a SEO, web development, performance web, sicurezza siti, marketing digitale e argomenti strettamente correlati
- Se l'utente fa domande NON pertinenti al SEO o al sito scansionato (es. cucina, sport, storia, matematica, altro), rispondi gentilmente:
  "⚠️ Mi dispiace, posso aiutarti solo con argomenti relativi al SEO e all'analisi del tuo sito web. Prova a farmi una domanda su SEO, performance, sicurezza o contenuti del tuo sito!"
- NON rispondere MAI a domande fuori tema, anche se l'utente insiste

REGOLE:
- Rispondi SEMPRE in italiano
- Sii pratico e diretto: fornisci soluzioni concrete, non teorie
- Quando hai contesto da scansioni reali, usalo per personalizzare le risposte
- Se non hai dati sufficienti, chiedi all'utente di effettuare una scansione
- Usa emoji per rendere le risposte più leggibili
- Formatta le risposte in Markdown per una migliore presentazione
- Se fornisci codice, specifica il linguaggio e dove inserirlo

{rag_context}"""


def _build_rag_context(
    user_message: str,
    scan_id: Optional[str] = None,
    domain: Optional[str] = None,
) -> str:
    """
    Build a RAG context string by querying both knowledge base and scan history.
    Returns formatted context for the system prompt.
    """
    context_parts = []
    
    # Level 1: SEO Knowledge Base
    try:
        kb_results = query_knowledge(user_message, n_results=3)
        if kb_results:
            kb_texts = []
            for r in kb_results:
                if r.get("distance", 1.0) < 1.5:
                    kb_texts.append(f"• [{r['title']}] {r['content']}")
            if kb_texts:
                context_parts.append(
                    "📚 KNOWLEDGE BASE SEO:\n" + "\n".join(kb_texts)
                )
    except Exception as e:
        logger.debug("Knowledge base query failed: %s", e)
    
    # Level 2: Scan History
    try:
        scan_results = query_scan_history(
            user_message,
            n_results=4,
            domain=domain,
            scan_id=scan_id,
        )
        if scan_results:
            scan_texts = []
            for r in scan_results:
                if r.get("distance", 1.0) < 1.5:
                    scan_texts.append(
                        f"• [{r.get('section', 'info')}] {r['content'][:500]}"
                    )
            if scan_texts:
                context_parts.append(
                    "📊 DATI DALLE SCANSIONI:\n" + "\n".join(scan_texts)
                )
    except Exception as e:
        logger.debug("Scan history query failed: %s", e)
    
    # Level 3: Uploaded PDF documents
    try:
        from app.core.vector_store import get_collection, get_embeddings
        doc_collection = get_collection("uploaded_documents")
        if doc_collection.count() > 0:
            emb = get_embeddings()
            q_vec = emb.embed_query(user_message)
            doc_results = doc_collection.query(
                query_embeddings=[q_vec],
                n_results=min(3, doc_collection.count()),
                include=["documents", "metadatas", "distances"],
            )
            if doc_results and doc_results["documents"] and doc_results["documents"][0]:
                doc_texts = []
                for i, doc in enumerate(doc_results["documents"][0]):
                    dist = doc_results["distances"][0][i] if doc_results["distances"] else 1.0
                    meta = doc_results["metadatas"][0][i] if doc_results["metadatas"] else {}
                    if dist < 1.5:
                        label = meta.get("label", meta.get("filename", "documento"))
                        doc_texts.append(f"• [{label}] {doc[:500]}")
                if doc_texts:
                    context_parts.append(
                        "📄 DOCUMENTI PDF CARICATI:\n" + "\n".join(doc_texts)
                    )
    except Exception as e:
        logger.debug("PDF documents query failed: %s", e)

    if context_parts:
        return "CONTESTO RECUPERATO (usa queste informazioni per rispondere):\n\n" + "\n\n---\n\n".join(context_parts)
    return ""


def get_conversation_history(conversation_id: str) -> list:
    """Get the conversation history for a given conversation_id."""
    return _conversations.get(conversation_id, [])


def clear_conversation(conversation_id: str):
    """Clear the conversation history for a given conversation_id."""
    if conversation_id in _conversations:
        del _conversations[conversation_id]


def chat_sync(
    message: str,
    conversation_id: str = "default",
    scan_id: Optional[str] = None,
    domain: Optional[str] = None,
) -> str:
    """
    Synchronous chat with RAG context.
    Returns the full response as a string.
    """
    # Build RAG context
    rag_context = _build_rag_context(message, scan_id=scan_id, domain=domain)
    
    # Build messages
    system_msg = CHAT_SYSTEM_PROMPT.format(rag_context=rag_context)
    
    messages = [SystemMessage(content=system_msg)]
    
    # Add conversation history
    history = _conversations[conversation_id]
    for msg in history[-MAX_HISTORY:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    # Add current message
    messages.append(HumanMessage(content=message))
    
    # Invoke LLM
    llm = get_shared_llm(streaming=False)
    response = llm.invoke(messages)
    answer = response.content
    
    # Save to history
    _conversations[conversation_id].append({"role": "user", "content": message})
    _conversations[conversation_id].append({"role": "assistant", "content": answer})
    
    # Trim history
    if len(_conversations[conversation_id]) > MAX_HISTORY * 2:
        _conversations[conversation_id] = _conversations[conversation_id][-MAX_HISTORY * 2:]
    
    return answer


async def chat_stream(
    message: str,
    conversation_id: str = "default",
    scan_id: Optional[str] = None,
    domain: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming chat with RAG context.
    Yields tokens as they are generated.
    """
    # Build RAG context
    rag_context = _build_rag_context(message, scan_id=scan_id, domain=domain)
    
    # Build messages
    system_msg = CHAT_SYSTEM_PROMPT.format(rag_context=rag_context)
    
    messages = [SystemMessage(content=system_msg)]
    
    # Add conversation history
    history = _conversations[conversation_id]
    for msg in history[-MAX_HISTORY:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    # Add current message
    messages.append(HumanMessage(content=message))
    
    # Stream LLM response
    llm = get_shared_llm(streaming=True)
    full_response = ""
    
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_response += token
            yield token
    
    # Save to history
    _conversations[conversation_id].append({"role": "user", "content": message})
    _conversations[conversation_id].append({"role": "assistant", "content": full_response})
    
    # Trim history
    if len(_conversations[conversation_id]) > MAX_HISTORY * 2:
        _conversations[conversation_id] = _conversations[conversation_id][-MAX_HISTORY * 2:]
