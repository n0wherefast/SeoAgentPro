from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_factory import get_shared_llm


ROADMAP_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un consulente SEO strategico che crea PIANI D'AZIONE completi e comprensibili.

Il tuo compito è analizzare i problemi trovati e creare una ROADMAP STRATEGICA che mostri:
1. La situazione attuale (problemi rilevati)
2. Il piano d'azione organizzato per priorità
3. Timeline realistica per ogni fase

Formato della risposta:

---

## 📊 Riepilogo Situazione

| Metrica | Valore |
|---------|--------|
| Problemi Critici | X |
| Problemi Medi | X |
| Problemi Minori | X |
| Punteggio Stimato | X/100 |

[Breve paragrafo sulla salute SEO generale del sito]

---

## 🔴 PRIORITÀ ALTA (Settimana 1)
*Problemi critici che impattano indicizzazione e ranking*

Per ogni problema:
1. **[Nome problema]**
   - 📖 Cosa significa: [spiegazione semplice]
   - ⚠️ Impatto: [conseguenze concrete]
   - ⏱️ Tempo stimato: [X minuti/ore]

---

## 🟡 PRIORITÀ MEDIA (Settimane 2-3)
*Miglioramenti importanti per ottimizzazione*

[stesso formato]

---

## 🟢 PRIORITÀ BASSA (Mese 2+)
*Ottimizzazioni avanzate e nice-to-have*

[stesso formato]

---

## 🎯 Risultati Attesi

[Cosa migliorerà dopo aver completato la roadmap]

---

## 💡 Consiglio Finale

[Un suggerimento strategico personalizzato]

---

Regole:
- Sii specifico e pratico
- Usa emoji per la leggibilità
- NON includere codice tecnico (c'è la sezione AutoFix per quello)
- Concentrati sulla STRATEGIA e le PRIORITÀ
- Dai timeline realistiche"""
    ),
    ("user",
     """PROBLEMI RILEVATI DALLA SCANSIONE:
{errors}

INFORMAZIONI PAGINA:
- URL: {url}
- Titolo: {title}
- Meta Description: {meta_description}

Crea una ROADMAP STRATEGICA completa con priorità e timeline."""
    )
])

def generate_roadmap(errors: list, page_data: dict):
    """
    Generate a strategic SEO roadmap with priorities and timeline.
    Returns user-friendly Markdown with action plan.
    """
    try:
        llm = get_shared_llm()
        
        # Sanitize page_data
        if page_data is None:
            page_data = {}
        
        # Extract key info
        url = page_data.get("url", "N/A")
        title = page_data.get("title", "N/A")
        meta_desc = page_data.get("meta_description", "N/A")
        
        # Format errors as list
        if not isinstance(errors, list):
            errors = []
        error_list = "\n".join(f"- {str(e)[:200]}" for e in errors[:20])
        
        print(f"[DEBUG] generate_roadmap: processing {len(errors)} errors")
        
        messages = ROADMAP_PROMPT.format_messages(
            errors=error_list or "Nessun errore critico rilevato",
            url=url,
            title=title,
            meta_description=meta_desc
        )
        
        print(f"[DEBUG] generate_roadmap: invoking LLM...")
        res = llm.invoke(messages)
        print(f"[DEBUG] generate_roadmap: LLM response length: {len(res.content)}")
        return res.content
    except Exception as e:
        print(f"[ERROR] generate_roadmap EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Roadmap generation failed: {str(e)[:200]}" 
