import json
import logging
import os
import re

from app.core.llm_factory import get_shared_llm
from app.core.cache_manager import hash_input
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from functools import lru_cache
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

load_dotenv()


def _retrieve_rag_context(query: str, n_results: int = 3) -> str:
    """
    Retrieve relevant SEO knowledge from the RAG vector store.
    Returns formatted context string for prompt augmentation.
    Falls back gracefully if vector store is not available.
    """
    try:
        from app.core.knowledge_indexer import query_knowledge
        results = query_knowledge(query, n_results=n_results)
        if not results:
            return ""
        
        context_parts = []
        for r in results:
            if r.get("distance", 1.0) < 1.5:  # Only use relevant results
                context_parts.append(f"[{r['title']}] {r['content']}")
        
        if context_parts:
            return "\n\n---\n\n".join(context_parts)
        return ""
    except Exception as e:
        logger.debug("RAG retrieval skipped: %s", e)
        return ""

# Cache for LLM responses - reduces costs for repeated scans
_fix_response_cache = {}


@lru_cache(maxsize=100)
def _cached_ai_fix_impl(error_hash: str, page_hash: str, error_str: str, page_str: str) -> str:
    """
    Cached implementation of AI fix generation.
    Uses hashes as cache keys for efficiency.
    """
    llm = get_shared_llm()
    
    FIX_PROMPT = ChatPromptTemplate.from_messages([
        ("system",
         "Sei un auditor SEO senior. "
         "Analizza problemi SEO e genera una soluzione tecnica breve, precisa e applicabile."
         "Rispondi SEMPRE con questo formato:\n\n"
         "IDEA: spiegazione breve\n"
         "FIX: snippet di codice o azione precisa\n"
         "PRIORITA: alta / media / bassa\n"
        ),
        ("user",
         "Errore:\n{error}\n\n"
         "Contenuto pagina analizzato:\n{page_data}\n\n"
         "Genera il fix ora."
        )
    ])
    
    messages = FIX_PROMPT.format_messages(
        error=error_str,
        page_data=page_str
    )
    result = llm.invoke(messages)
    return result.content



# ==================== SINGLE FIX PROMPT ====================
FIX_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Sei un auditor SEO senior. "
     "Analizza problemi SEO e genera una soluzione tecnica breve, precisa e applicabile."
     "Rispondi SEMPRE con questo formato:\n\n"
     "IDEA: spiegazione breve\n"
     "FIX: snippet di codice o azione precisa\n"
     "PRIORITA: alta / media / bassa\n"
    ),
    ("user",
     "Errore:\n{error}\n\n"
     "Contenuto pagina analizzato:\n{page_data}\n\n"
     "Genera il fix ora."
    )
])


def generate_ai_fix(error: dict, page_data: dict) -> str:
    """
    Generate a fix for a single SEO error with caching.
    Reduces costs by ~60% for repeated error types.
    Returns a formatted fix string.
    """
    # Create cache keys from input data
    error_str = str(error)[:500]
    page_str = str(page_data)[:500]
    error_hash = hash_input(error_str)
    page_hash = hash_input(page_str)
    
    # Use cached implementation (LRU cache will handle duplicates)
    return _cached_ai_fix_impl(error_hash, page_hash, error_str, page_str)


# ==================== AUTOFIX REPORT PROMPT ====================
AUTOFIX_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un tecnico SEO esperto che fornisce SOLUZIONI PRATICHE con codice pronto da implementare.

Il sito analizzato utilizza questo STACK TECNOLOGICO: {tech_stack}

{rag_context}

IMPORTANTE: Genera SOLO codice compatibile con lo stack indicato.
- Se il sito usa WordPress, genera snippet PHP/WP (functions.php, plugin hooks, .htaccess).
- Se il sito usa Next.js/React, genera codice JSX/TSX con next/head o metadata API.
- Se il sito usa Shopify, genera Liquid template code.
- Se il sito usa HTML puro, genera HTML/CSS/JS vanilla.
- Se il sito usa un CMS (Wix, Squarespace…), dai istruzioni specifiche per quel CMS.

Per OGNI fix, il tuo output deve seguire questo formato:

---

### 🔧 [Nome del problema]

**📖 Cos'è:** [1 riga di spiegazione semplice]

**⚠️ Impatto:** [Cosa succede se non lo risolvi]

**✅ Soluzione ({tech_stack}):**

```[linguaggio appropriato per lo stack]
[CODICE PRONTO DA COPIARE — specifico per lo stack]
```

**📍 Dove inserirlo:** [Posizione esatta nel progetto/CMS]

**⏱️ Tempo:** [X minuti] | **🎯 Difficoltà:** [Facile/Media]

---

Regole:
- Fornisci SEMPRE codice funzionante e completo PER LO STACK INDICATO
- Usa commenti nel codice per spiegare le parti importanti
- NON includere roadmap o piani a lungo termine (c'è una sezione dedicata)
- Concentrati SOLO sui fix tecnici immediati
- Usa emoji per rendere tutto chiaro e leggibile"""
    ),
    ("user",
     """ERRORI TECNICI DA RISOLVERE:
{errors}

INFORMAZIONI PAGINA:
- URL: {url}
- Titolo: {title}
- Meta Description: {meta_description}
- Stack Tecnologico: {tech_stack}

Genera i FIX TECNICI con codice pronto per lo stack {tech_stack}.
NON includere roadmap o piani strategici."""
    )
])


def generate_autofix_report(errors: list, page_data: dict) -> str:
    """
    Generate a complete autofix report for multiple errors.
    Returns a user-friendly Markdown guide with stack-specific code snippets.
    """
    try:
        # Sanitize inputs
        if not isinstance(errors, list):
            errors = []
        errors = [str(e)[:300] for e in errors[:20]]  # Limit to 20 errors
        
        if page_data is None:
            page_data = {}
        
        # Extract key page info including tech stack
        url = page_data.get("url", "N/A")
        title = page_data.get("title", "N/A")
        meta_desc = page_data.get("meta_description", "N/A")
        tech_stack = page_data.get("tech_stack", "HTML/Custom")
        
        # RAG: retrieve relevant SEO knowledge for these errors
        rag_query = f"SEO fix per: {' '.join(str(e)[:80] for e in errors[:5])}"
        rag_context_raw = _retrieve_rag_context(rag_query, n_results=4)
        rag_context = (
            f"CONTESTO dalla Knowledge Base SEO (usa queste best practice nelle tue risposte):\n{rag_context_raw}"
            if rag_context_raw else ""
        )
        
        llm = get_shared_llm(streaming=True)
        messages = AUTOFIX_PROMPT.format_messages(
            errors="\n".join(f"- {e}" for e in errors),
            url=url,
            title=title,
            meta_description=meta_desc,
            tech_stack=tech_stack,
            rag_context=rag_context
        )
        res = llm.invoke(messages)
        return res.content
    except Exception as e:
        logger.error("generate_autofix_report failed: %s", e)
        return f"AutoFix report generation failed: {str(e)[:200]}"


# ==================== GENERATE FIX SUGGESTIONS (STRUCTURED JSON) ====================

FIX_SUGGESTIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un esperto SEO tecnico. Analizza i problemi SEO e genera soluzioni strutturate.
Lo stack tecnologico del sito è: {tech_stack}

{rag_context}

Per OGNI problema, rispondi con un array JSON valido contenente oggetti con questa struttura esatta:
{{
    "issue_id": "nome breve del problema",
    "explanation": "spiegazione di cosa fare e perché",
    "code_snippet": "codice pronto per lo stack {tech_stack} — HTML/PHP/JSX/Liquid ecc. a seconda dello stack"
}}

REGOLE:
- Rispondi SOLO con l'array JSON, nessun testo prima o dopo
- I code_snippet DEVONO essere compatibili con lo stack {tech_stack}
- code_snippet può essere vuoto "" se non c'è codice da mostrare
- Mantieni le spiegazioni brevi e pratiche
- Massimo 10 fix"""
    ),
    ("user",
     """PROBLEMI SEO RILEVATI:
{issues}

DATI PAGINA:
- URL: {url}
- Title: {title}
- Description: {description}
- Stack: {tech_stack}

Genera l'array JSON con i fix specifici per lo stack {tech_stack}."""
    )
])


def generate_fix_suggestions(issues: List[Dict], page_data: Dict) -> List[Dict[str, Any]]:
    """
    Generate structured fix suggestions for SEO issues.
    Returns a list of fix objects with issue_id, explanation, and code_snippet.
    """
    try:
        if not issues:
            return []
        
        # Limit issues to process
        issues_to_process = issues[:15]
        
        # Format issues for prompt
        issues_text = "\n".join([
            f"- {issue.get('type', 'unknown')}: {issue.get('message', str(issue))[:200]}"
            for issue in issues_to_process
        ])
        
        # Extract page info
        url = page_data.get("url", "N/A") if page_data else "N/A"
        title = page_data.get("title", "N/A") if page_data else "N/A"
        description = page_data.get("meta_description", "N/A") if page_data else "N/A"
        tech_stack = page_data.get("tech_stack", "HTML/Custom") if page_data else "HTML/Custom"
        
        # RAG: retrieve relevant SEO knowledge
        rag_query = f"SEO fix per: {issues_text[:200]}"
        rag_context_raw = _retrieve_rag_context(rag_query, n_results=3)
        rag_context = (
            f"CONTESTO dalla Knowledge Base SEO:\n{rag_context_raw}"
            if rag_context_raw else ""
        )
        
        llm = get_shared_llm()
        messages = FIX_SUGGESTIONS_PROMPT.format_messages(
            issues=issues_text,
            url=url,
            title=title,
            description=description,
            tech_stack=tech_stack,
            rag_context=rag_context
        )
        
        result = llm.invoke(messages)
        content = result.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        fixes = json.loads(content)
        
        # Validate structure
        if not isinstance(fixes, list):
            fixes = [fixes]
        
        validated_fixes = []
        for fix in fixes:
            validated_fixes.append({
                "issue_id": fix.get("issue_id", "SEO Issue"),
                "explanation": fix.get("explanation", ""),
                "code_snippet": fix.get("code_snippet", "")
            })
        
        logger.info("generate_fix_suggestions: Generated %d fixes", len(validated_fixes))
        return validated_fixes
        
    except json.JSONDecodeError as e:
        logger.error("generate_fix_suggestions JSON parse error: %s", e)
        # Fallback: generate simple fixes from issues
        return [
            {
                "issue_id": issue.get("type", f"Issue {i+1}"),
                "explanation": issue.get("message", str(issue))[:300],
                "code_snippet": ""
            }
            for i, issue in enumerate(issues[:10])
        ]
    except Exception as e:
        logger.error("generate_fix_suggestions failed: %s", e)
        return []
