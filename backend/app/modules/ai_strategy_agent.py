import logging

from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_factory import get_shared_llm

logger = logging.getLogger(__name__)

STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """Sei un SEO Strategist esperto che spiega in modo SEMPLICE e PRATICO.
Il tuo pubblico NON è tecnico - sono imprenditori, marketer, proprietari di siti web.

REGOLE:
- Usa linguaggio SEMPLICE, evita termini tecnici
- Se usi termini SEO, spiega cosa significano
- Dai AZIONI CONCRETE che chiunque può fare
- Sii SPECIFICO: invece di "migliora i contenuti" → "aggiungi una sezione FAQ con 5 domande"
- Usa emoji per rendere il testo più leggibile
- Scrivi in ITALIANO
- Formatta con Markdown: usa ## per sezioni, **grassetto** per punti chiave, - per elenchi
"""
    ),
    ("user",
     """Analizza questi dati e genera una STRATEGIA SEO PRATICA.

## SITUAZIONE ATTUALE

**IL TUO SITO:**
- Punteggio complessivo: {my_score}/100
- Authority: {my_authority} | Content: {my_content} | Technical: {my_technical}

**IL COMPETITOR:**
- Punteggio complessivo: {comp_score}/100
- Authority: {comp_authority} | Content: {comp_content} | Technical: {comp_technical}

**CHI VINCE:** {winner}

**KEYWORD CHE TI MANCANO (Gap):**
{keyword_gap}

**KEYWORD IN COMUNE:**
{keyword_overlap}

---

Genera la strategia in questo formato ESATTO:

## 🎯 Verdetto Rapido
[1-2 frasi: chi sta vincendo e perché, cosa devi fare SUBITO]

## 💪 I Tuoi Punti di Forza
[Cosa stai facendo bene - elenca 2-3 punti con spiegazione]

## ⚠️ Dove Devi Migliorare
[Cosa ti manca rispetto al competitor - elenca 2-3 punti con spiegazione SEMPLICE]

## 📝 Piano d'Azione Immediato

### Settimana 1: Quick Wins
[3 azioni FACILI che puoi fare subito, spiega COME farle]

### Settimana 2-3: Contenuti
[2-3 contenuti/pagine da creare, spiega COSA scrivere]

### Mese 2: Crescita
[2-3 azioni per costruire autorità, spiega PERCHÉ funzionano]

## ✅ Checklist Finale
[5-7 task numerati, brevi e azionabili]
"""
    )
])
 

def _safe_str(value) -> str:
    """Converte qualsiasi valore in stringa sicura."""
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        # Se è un dict, prova a estrarre "kw" o restituisci una descrizione
        if "kw" in value:
            return str(value["kw"])
        return str(list(value.values())[0]) if value else "N/A"
    if isinstance(value, (list, tuple)):
        return ", ".join(_safe_str(v) for v in value[:5])
    return str(value)


def _safe_keyword_list(keywords: list) -> list:
    """Converte una lista di keyword (potenzialmente oggetti) in lista di stringhe."""
    result = []
    for kw in keywords:
        if isinstance(kw, dict):
            # Estrai il campo "kw" se presente
            result.append(str(kw.get("kw", kw.get("keyword", str(kw)))))
        elif isinstance(kw, str):
            result.append(kw)
        else:
            result.append(str(kw))
    return result


def generate_strategy(scan: dict, competitor: dict, compare: dict):
    """Genera strategia SEO user-friendly usando i risultati."""
    try:
        # Estrai dati rilevanti dal compare
        ranking = compare.get("ranking", {}) if compare else {}
        keyword_gap = compare.get("keyword_gap", []) if compare else []
        keyword_overlap = compare.get("keyword_overlap", []) if compare else []
        
        # ✅ Normalizza keyword a stringhe
        keyword_gap = _safe_keyword_list(keyword_gap)
        keyword_overlap = _safe_keyword_list(keyword_overlap)
        
        # Score dal ranking
        my_score = ranking.get("my_overall", "N/A") if ranking else "N/A"
        comp_score = ranking.get("comp_overall", "N/A") if ranking else "N/A"
        winner = ranking.get("winner", "N/A") if ranking else "N/A"
        
        # Scores dettagliati
        my_scores = ranking.get("my_scores", {}) if ranking else {}
        comp_scores = ranking.get("comp_scores", {}) if ranking else {}
        
        # ✅ Estrai valori sicuri dai scores
        my_authority = _safe_str(my_scores.get("authority"))
        my_content = _safe_str(my_scores.get("content"))
        my_technical = _safe_str(my_scores.get("technical"))
        comp_authority = _safe_str(comp_scores.get("authority"))
        comp_content = _safe_str(comp_scores.get("content"))
        comp_technical = _safe_str(comp_scores.get("technical"))
        
        # Formatta keyword gap (max 15)
        gap_str = ", ".join(keyword_gap[:15]) if keyword_gap else "Nessun gap rilevato"
        if len(keyword_gap) > 15:
            gap_str += f" (+{len(keyword_gap) - 15} altre)"
        
        # Formatta keyword overlap (max 10)
        overlap_str = ", ".join(keyword_overlap[:10]) if keyword_overlap else "Nessuna keyword in comune"
        if len(keyword_overlap) > 10:
            overlap_str += f" (+{len(keyword_overlap) - 10} altre)"
        
        # Debug log
        logger.debug("AI Strategy input: my=%s, comp=%s", my_score, comp_score)
        logger.debug("Keywords gap: %s...", gap_str[:100])
        
        llm = get_shared_llm()
        messages = STRATEGY_PROMPT.format_messages(
            my_score=_safe_str(my_score),
            comp_score=_safe_str(comp_score),
            winner="Tu" if winner == "you" else "Competitor" if winner == "competitor" else "Parità",
            my_authority=my_authority,
            my_content=my_content,
            my_technical=my_technical,
            comp_authority=comp_authority,
            comp_content=comp_content,
            comp_technical=comp_technical,
            keyword_gap=gap_str,
            keyword_overlap=overlap_str,
        )
        res = llm.invoke(messages)
        return res.content
    except Exception as e:
        logger.error("generate_strategy failed: %s", e)
        return f"Strategy generation failed: {str(e)[:200]}"
