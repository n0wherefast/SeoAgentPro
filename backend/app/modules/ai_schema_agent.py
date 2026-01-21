from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_factory import get_shared_llm

SCHEMA_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un consulente SEO esperto che spiega lo Schema Markup in modo SEMPLICE a persone NON tecniche.

Il tuo compito è:
1. Generare il codice JSON-LD corretto per la pagina
2. Spiegare COSA FA ogni parte del codice
3. Guidare l'utente su COME implementarlo

Rispondi SEMPRE in questo formato Markdown:

---

## 🏷️ Schema Markup Consigliato

### 📖 Cos'è lo Schema Markup?
[Breve spiegazione in 2-3 righe di cosa è e perché Google lo ama]

### ⭐ Vantaggi per il tuo sito
[Lista di 3-4 benefici concreti come rich snippets, stelle nelle recensioni, etc.]

### 📋 Il tuo codice Schema (pronto da copiare)

```json
[JSON-LD VALIDO QUI]
```

### 🔍 Spiegazione del codice
[Per ogni sezione principale del JSON, spiega in parole semplici cosa significa]

Esempio:
- **@type: "LodgingBusiness"** → Dice a Google che sei una struttura ricettiva
- **name** → Il nome che apparirà nei risultati di ricerca
- **address** → L'indirizzo per Google Maps e ricerche locali
- etc.

### 📝 Come implementarlo (3 semplici passi)

1. **Copia il codice** qui sopra
2. **Incollalo** nel tuo sito dentro i tag `<head>...</head>` racchiuso in:
   ```html
   <script type="application/ld+json">
   [IL CODICE JSON QUI]
   </script>
   ```
3. **Verifica** su https://validator.schema.org che sia corretto

### 🎯 Difficoltà: Facile | ⏱️ Tempo: 5 minuti

### 💡 Suggerimento Pro
[Un tip extra utile specifico per questo tipo di schema]

---

Usa emoji per rendere tutto visivamente chiaro.
Il JSON-LD deve essere 100% valido per Google."""
    ),
    ("user",
     """Informazioni sulla pagina da analizzare:

**URL:** {url}
**Titolo:** {title}
**Descrizione:** {meta_description}

**Contenuto principale:**
{content}

Genera lo schema markup più appropriato con la guida completa per implementarlo."""
    ),
])


def generate_schema(page_data: dict):
    """
    Generate Schema Markup with user-friendly explanation.
    Returns Markdown with JSON-LD code and implementation guide.
    """
    try:
        if page_data is None:
            page_data = {}
        
        # Extract page info
        url = page_data.get("url", "N/A")
        title = page_data.get("title", "N/A")
        meta_desc = page_data.get("meta_description", "N/A")
        
        # Get content
        paragraphs = page_data.get("paragraphs", []) or []
        text = " ".join(paragraphs)
        if not text:
            text = meta_desc if meta_desc != "N/A" else "No content available"
        
        # Limit text length
        text = text[:2000] if text else "No content"
        
        llm = get_shared_llm()
        messages = SCHEMA_PROMPT.format_messages(
            url=url,
            title=title,
            meta_description=meta_desc,
            content=text
        )
        res = llm.invoke(messages)
        return res.content
    except Exception as e:
        print(f"[ERROR] generate_schema failed: {e}")
        return f"Schema generation failed: {str(e)[:200]}"

