import logging

from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_factory import get_shared_llm

logger = logging.getLogger(__name__)

EXPAND_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Sei un SEO content strategist. Espandi il testo migliorando SEO, leggibilità e includendo keyword rilevanti. "
     "La scrittura deve essere naturale, fluida e non robotica."
    ),
    ("user",
     "Testo originale:\n{content}\n\n"
     "Keyword target:\n{keywords}\n\n"
     "Riscrivi ed espandi il contenuto rendendolo più efficace."
    )
])

def expand_content(page_data: dict, keywords: list):
    try:
        llm = get_shared_llm()
        
        # Safely extract text
        if page_data is None:
            page_data = {}
        
        text = " ".join(page_data.get("paragraphs", []) or [])
        if not text:
            text = page_data.get("meta_description", "No content found")
        
        # Limit text length
        text = text[:3000] if text else "No content"
        
        # Ensure keywords is a list
        kw_list = keywords if isinstance(keywords, list) else []
        kw_str = ", ".join(str(k)[:50] for k in kw_list[:20])  # Limit to 20 keywords
        
        messages = EXPAND_PROMPT.format_messages(
            content=text,
            keywords=kw_str or "generic keywords"
        )
        res = llm.invoke(messages)
        return res.content
    except Exception as e:
        logger.error("expand_content failed: %s", e)
        return f"Content expansion failed: {str(e)[:200]}"
