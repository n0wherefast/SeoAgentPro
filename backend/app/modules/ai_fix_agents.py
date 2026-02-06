from app.core.llm_factory import get_shared_llm
from app.core.cache_manager import hash_input
from langchain_core.prompts import ChatPromptTemplate
import os
import json
import re
from dotenv import load_dotenv
from functools import lru_cache
from typing import List, Dict, Any

load_dotenv()

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

Il tuo compito è fornire FIX TECNICI IMMEDIATI per ogni errore, con:
- Codice pronto da copiare e incollare
- Istruzioni precise su dove metterlo
- Spiegazione semplice di cosa fa

Formato per OGNI fix:

---

### 🔧 [Nome del problema]

**📖 Cos'è:** [1 riga di spiegazione semplice]

**⚠️ Impatto:** [Cosa succede se non lo risolvi]

**✅ Soluzione:**

```[linguaggio]
[CODICE PRONTO DA COPIARE]
```

**📍 Dove inserirlo:** [Posizione esatta nel sito]

**⏱️ Tempo:** [X minuti] | **🎯 Difficoltà:** [Facile/Media]

---

Regole:
- Fornisci SEMPRE codice funzionante e completo
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

Genera i FIX TECNICI con codice pronto per ogni errore.
NON includere roadmap o piani strategici."""
    )
])


def generate_autofix_report(errors: list, page_data: dict) -> str:
    """
    Generate a complete autofix report for multiple errors.
    Returns a user-friendly Markdown guide with detailed explanations.
    """
    try:
        # Sanitize inputs
        if not isinstance(errors, list):
            errors = []
        errors = [str(e)[:300] for e in errors[:20]]  # Limit to 20 errors
        
        if page_data is None:
            page_data = {}
        
        # Extract key page info
        url = page_data.get("url", "N/A")
        title = page_data.get("title", "N/A")
        meta_desc = page_data.get("meta_description", "N/A")
        
        llm = get_shared_llm(streaming=True)
        messages = AUTOFIX_PROMPT.format_messages(
            errors="\n".join(f"- {e}" for e in errors),
            url=url,
            title=title,
            meta_description=meta_desc
        )
        res = llm.invoke(messages)
        return res.content
    except Exception as e:
        print(f"[ERROR] generate_autofix_report failed: {e}")
        return f"AutoFix report generation failed: {str(e)[:200]}"


# ==================== GENERATE FIX SUGGESTIONS (STRUCTURED JSON) ====================

FIX_SUGGESTIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un esperto SEO tecnico. Analizza i problemi SEO e genera soluzioni strutturate.

Per OGNI problema, rispondi con un array JSON valido contenente oggetti con questa struttura esatta:
{{
    "issue_id": "nome breve del problema",
    "explanation": "spiegazione di cosa fare e perché",
    "code_snippet": "codice HTML/meta tag da aggiungere o modificare (se applicabile)"
}}

REGOLE:
- Rispondi SOLO con l'array JSON, nessun testo prima o dopo
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

Genera l'array JSON con i fix."""
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
        
        llm = get_shared_llm()
        messages = FIX_SUGGESTIONS_PROMPT.format_messages(
            issues=issues_text,
            url=url,
            title=title,
            description=description
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
        
        print(f"[generate_fix_suggestions] Generated {len(validated_fixes)} fixes")
        return validated_fixes
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] generate_fix_suggestions JSON parse error: {e}")
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
        print(f"[ERROR] generate_fix_suggestions failed: {e}")
        return []
