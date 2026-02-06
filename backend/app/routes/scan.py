
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from app.modules.scraper import scrape_url
from app.modules.seo_rules import SEOScoringEngine
from app.modules.seo_detection_unified import detect_seo_issues_unified
from app.modules.competitor.competitor_analyzer import analyze_competitors
from app.modules.seo_technical import run_technical_checks
from app.modules.competitor.lighthouse_client import run_performance_engine
from app.modules.authority_engine import run_authority_engine
from app.modules.ai_fix_agents import generate_ai_fix
from app.utils.validators import validate_url
import json
import logging
import itertools

logger = logging.getLogger(__name__)

router = APIRouter()

# Global SSE event counter for event-id support
_sse_counter = itertools.count(1)

# =========================
# 🔹 QUICK SCAN (SSE STREAMING)
# =========================
@router.get("/quick-scan")
async def quick_scan(url: str):
    """Quick scan: scrape + technical + performance + seo_score (no competitor analysis)"""
    # Validate URL
    try:
        url = validate_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def event_generator():
        try:
            logger.info(f"🚀 QUICK-SCAN START: url={url}")
            
            # 1) SCRAPE
            scraped = scrape_url(url)
            # Strip raw HTML from SSE payload (too large for frontend)
            scrape_payload = {k: v for k, v in scraped.items() if k != "html_content"}
            yield sse("scrape", scrape_payload)

            # 2) ONPAGE ERRORS (using unified detection)
            onpage_errors = detect_seo_issues_unified(scraped)
            yield sse("onpage_errors", onpage_errors)

            # 3) TECHNICAL
            technical = run_technical_checks(scraped, url)
            technical_errors = technical["technical_errors"]
            yield sse("technical", technical)

            # 4) PERFORMANCE
            perf_score = None
            try:
                performance = run_performance_engine(url)
                perf_score = performance.get("performance_score")
                logger.info(f"PERFORMANCE: score={perf_score}")
            except Exception as e:
                logger.error(f"PERFORMANCE failed: {e}")
                performance = {"performance_score": None, "metrics": {}, "error": str(e)}
            yield sse("performance", performance)

            # 5) AUTHORITY
            try:
                authority = run_authority_engine(scraped, None)
                logger.info(f"AUTHORITY: score={authority.get('your_authority')}")
            except Exception as e:
                logger.error(f"AUTHORITY failed: {e}")
                authority = {"your_authority": None, "competitor_authority": None, "error": str(e)}
            yield sse("authority", authority)

            # 6) SEO SCORE
            all_errors = technical_errors + onpage_errors
            seo_engine = SEOScoringEngine(all_errors, performance_score=perf_score)
            seo_score = seo_engine.generate_output()
            yield sse("seo_score", seo_score)

            # 7) DONE
            from urllib.parse import urlparse as _urlparse
            done_payload = {
                "status": "completed",
                "domain": _urlparse(url).netloc,
                "url": url,
                "seo_score": seo_score.get("score") if isinstance(seo_score, dict) else None,
            }
            yield sse("done", done_payload)
            logger.info("✅ QUICK-SCAN COMPLETED")

        except Exception as e:
            logger.error(f"❌ ERROR in quick_scan: {str(e)}", exc_info=True)
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

# =========================
# 🔹 HELPER SSE
# =========================
def sse(event: str, data):
    """
    Formato SSE con event-id e retry per supportare resume dopo disconnessione.
    """
    try:
        event_id = next(_sse_counter)
        if isinstance(data, str):
            payload = {"content": data}
        elif isinstance(data, (dict, list)):
            payload = data
        else:
            payload = {"content": str(data)}

        json_str = json.dumps(payload, ensure_ascii=False)
        return f"id: {event_id}\nretry: 5000\nevent: {event}\ndata: {json_str}\n\n"
    except Exception as e:
        logger.error(f"SSE serialization failed for event '{event}': {e}")
        fallback = {"content": f"Error in {event}: {str(e)[:100]}"}
        json_str = json.dumps(fallback, ensure_ascii=False)
        return f"event: {event}\ndata: {json_str}\n\n"
