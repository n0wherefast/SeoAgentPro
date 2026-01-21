
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
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# =========================
# 🔹 CORS OPTIONS PREFLIGHT
# =========================
@router.options("/quick-scan")
async def options_quick_scan():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

# =========================
# 🔹 QUICK SCAN (SSE STREAMING)
# =========================
@router.get("/quick-scan")
async def quick_scan(url: str):
    """Quick scan: scrape + technical + performance + seo_score + ai_fixes (no competitor analysis)"""
    async def event_generator():
        try:
            logger.info(f"🚀 QUICK-SCAN START: url={url}")
            print(f"\n🚀 QUICK-SCAN START: {url}\n")
            
            # 1) SCRAPE
            scraped = scrape_url(url)
            yield sse("scrape", scraped)

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
                print(f"[DEBUG] PERFORMANCE: score={perf_score}, full_data={performance}")
            except Exception as e:
                print(f"[ERROR] PERFORMANCE failed: {e}")
                performance = {"performance_score": None, "metrics": {}, "error": str(e)}
            yield sse("performance", performance)

            # 5) AUTHORITY
            try:
                authority = run_authority_engine(scraped, None)
                auth_score = authority.get("your_authority")
                print(f"[DEBUG] AUTHORITY: score={auth_score}, full_data={authority}")
            except Exception as e:
                print(f"[ERROR] AUTHORITY failed: {e}")
                authority = {"your_authority": None, "competitor_authority": None, "error": str(e)}
            yield sse("authority", authority)

            # 6) SEO SCORE
            all_errors = technical_errors + onpage_errors
            seo_engine = SEOScoringEngine(all_errors, performance_score=perf_score)
            seo_score = seo_engine.generate_output()
            yield sse("seo_score", seo_score)

            # 7) AI FIXES
            print(f"[DEBUG] Generating AI fixes for {len(all_errors)} errors...")
            # ai_fixes = []
            # for err in all_errors[:10]:  # Limita a 10 fix per velocità
            #     try:
            #         ai_fix = generate_ai_fix(err, scraped)
            #         ai_fixes.append({
            #             "error_id": err.get("id"),
            #             "ai_fix": ai_fix
            #         })
            #     except Exception as e:
            #         print(f"[ERROR] AI fix for {err.get('id')} failed: {e}")
            #         ai_fixes.append({
            #             "error_id": err.get("id"),
            #             "ai_fix": f"Fix generation failed: {str(e)[:100]}"
            #         })
            # yield sse("ai_fixes", ai_fixes)

            # 8) DONE
            yield sse("done", {"status": "completed"})
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
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )

# =========================
# 🔹 HELPER SSE
# =========================
def sse(event: str, data):
    """
    Formato SSE: event: xxx\ndata: {...json...}\n\n
    Assicura che data sia sempre una struttura valida (dict o string wrappato in dict)
    """
    try:
        # Se data è una stringa, wrappala in un dict
        if isinstance(data, str):
            payload = {"content": data}
        # Se è già un dict o una lista, serializza direttamente
        elif isinstance(data, (dict, list)):
            payload = data
        else:
            # Fallback: stringify
            payload = {"content": str(data)}

        json_str = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {json_str}\n\n"
    except Exception as e:
        print(f"[ERROR] SSE serialization failed for event '{event}': {e}")
        # Fallback: ritorna un dict di errore
        fallback = {"content": f"Error in {event}: {str(e)[:100]}"}
        json_str = json.dumps(fallback, ensure_ascii=False)
        return f"event: {event}\ndata: {json_str}\n\n"


# async def scan_website(data: dict):
#     url = data.get("url")
#     competitor = data.get("competitor_url")

#     if not url:
#         raise HTTPException(status_code=400, detail="URL mancante.")

#     # 1) SCRAPE
#     scraped = scrape_url(url)

#     # 2) ON-PAGE SEO ENGINE
#     onpage_errors = detect_seo_issues_unified(scraped)

#     # 3) TECHNICAL SEO
#     technical = run_technical_checks(scraped, url)
#     technical_errors = technical["technical_errors"]

#     # MERGE ERRORI
#     all_errors = technical_errors + onpage_errors

#     # 4) PERFORMANCE ENGINE (LIGHTHOUSE)
#     performance = run_performance_engine(url)
#     perf_score = performance.get("performance_score")

#     # 5) SCORING ENGINE 2.0
#     engine = SEOScoringEngine(all_errors, performance_score=perf_score)
#     seo_report = engine.generate_output()

#     # 6) COMPETITOR ANALYSIS + AUTHORITY
#     competitor_report = None
#     authority_report = None

#     # AI FIXES
#     ai_fixes = []
#     for err in all_errors:
#         ai_fixes.append({
#             "error_id": err.get("id"),
#             "ai_fix": generate_ai_fix(err, scraped)
#         })


#     if competitor:
#         competitor_scraped = scrape_url(competitor)
#         competitor_report = analyze_competitors(scraped, competitor_scraped)
#         authority_report = run_authority_engine(scraped, competitor_scraped)
#     else:
#         authority_report = run_authority_engine(scraped, None)

#     # 7) RETURN JSON COMPLETO
#     return {
#         "url": url,
#         "scraped": scraped,
#         "onpage_errors": onpage_errors,
#         "technical": technical,
#         "performance": performance,
#         "seo": seo_report,
#         "authority": authority_report,
#         "competitor": competitor_report,
#         "ai_fixes": ai_fixes

#     }
