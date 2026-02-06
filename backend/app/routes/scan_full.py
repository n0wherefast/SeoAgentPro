

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from app.modules.scraper import smart_scrape_url
from app.modules.seo_detection_unified import detect_seo_issues_unified
from app.modules.seo_technical import run_technical_checks
from app.modules.competitor.lighthouse_client import run_performance_engine
from app.modules.authority_engine import run_authority_engine
from app.modules.seo_rules import SEOScoringEngine
from app.modules.competitor.ranking import rank_competitor, compute_simple_scores
from app.modules.competitor.radar import radar_payload
import os
import json
import time
import asyncio
import logging
import re

# Lazy imports for AI modules (imported only when needed)
# This reduces startup time and memory footprint for simple scans

logger = logging.getLogger(__name__)

router = APIRouter()

# =========================
# 🔹 KEYWORD ANALYSIS HELPER
# =========================
def analyze_keyword_presence(scraped: dict, keywords: list) -> dict:
    """
    Analizza la presenza delle keyword target nel contenuto della pagina.
    Restituisce un report dettagliato su dove ogni keyword appare.
    """
    if not keywords or not scraped:
        return {"keywords": [], "summary": "No keywords to analyze"}
    
    title = (scraped.get("title") or "").lower()
    meta_desc = (scraped.get("meta_description") or "").lower()
    h1_list = [h.lower() for h in (scraped.get("h1") or [])]
    h2_list = [h.lower() for h in (scraped.get("h2") or [])]
    paragraphs = " ".join(scraped.get("paragraphs") or []).lower()
    alt_texts = " ".join(scraped.get("images_alt") or []).lower()
    url = (scraped.get("url") or "").lower()
    
    results = []
    total_found = 0
    
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
            
        presence = {
            "keyword": kw,
            "in_title": kw_lower in title,
            "in_meta_description": kw_lower in meta_desc,
            "in_h1": any(kw_lower in h for h in h1_list),
            "in_h2": any(kw_lower in h for h in h2_list),
            "in_content": kw_lower in paragraphs,
            "in_url": kw_lower in url,
            "in_alt_text": kw_lower in alt_texts,
            "content_count": len(re.findall(re.escape(kw_lower), paragraphs))
        }
        
        # Calculate score (0-100) based on presence
        score = 0
        if presence["in_title"]: score += 25
        if presence["in_meta_description"]: score += 20
        if presence["in_h1"]: score += 20
        if presence["in_h2"]: score += 10
        if presence["in_content"]: score += 15
        if presence["in_url"]: score += 5
        if presence["in_alt_text"]: score += 5
        
        presence["optimization_score"] = min(score, 100)
        presence["status"] = "optimized" if score >= 60 else "needs_work" if score >= 30 else "missing"
        
        if score > 0:
            total_found += 1
        
        results.append(presence)
    
    return {
        "keywords": results,
        "total_keywords": len(keywords),
        "keywords_found": total_found,
        "coverage_percent": round(total_found / len(keywords) * 100) if keywords else 0,
        "summary": f"{total_found}/{len(keywords)} keywords trovate nel contenuto"
    }

# =========================
# 🔹 CORS OPTIONS PREFLIGHT
# =========================
@router.options("/scan-full/stream")
async def options_scan_full():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

# =========================
# 🔹 STREAMING SSE VERSION
# =========================
@router.get("/scan-full/stream")
async def scan_full_stream(
    request: Request,
    url: str,
    competitor_url: str | None = None,
    keywords: str | None = None
):
    # Parse keywords from comma-separated string
    target_keywords = [k.strip() for k in (keywords or "").split(",") if k.strip()]
    
    async def event_generator():
        try:
            # Log parameters per debug
            logger.info(f"🔍 SCAN-FULL START: url={url}, competitor_url={competitor_url}, keywords={target_keywords}")
            print(f"\n\n🔍🔍🔍 SCAN-FULL START: url={url}, competitor_url={competitor_url}, keywords={target_keywords}\n\n")
            
            # 1) SCRAPE
            scraped = smart_scrape_url(url)
            yield sse("scrape", scraped)

            # 3) TECHNICAL
            technical = run_technical_checks(scraped, url)
            technical_errors = technical["technical_errors"]
            # Unisci i campi tecnici a scraped per la detection
            scraped.update(technical["technical_flags"])

            # 2) ONPAGE ERRORS (using unified detection)
            onpage_errors = detect_seo_issues_unified(scraped)
            yield sse("onpage_errors", onpage_errors)

            # 2.5) KEYWORD TARGET ANALYSIS (if keywords provided)
            if target_keywords:
                keyword_presence = analyze_keyword_presence(scraped, target_keywords)
                yield sse("keyword_analysis", keyword_presence)

            yield sse("technical", technical)
            technical = run_technical_checks(scraped, url)
            technical_errors = technical["technical_errors"]
            yield sse("technical", technical)

            # 3b) SITEMAP ANALYSIS (come in agent_scan)
            from app.modules.seo_technical import analyze_sitemap
            sitemap_url = technical.get("sitemap_url")
            if sitemap_url:
                sitemap_data = analyze_sitemap(sitemap_url)
                yield sse("sitemap_analysis", sitemap_data)
            else:
                yield sse("sitemap_analysis", {
                    "sitemap_url": None,
                    "is_index": False,
                    "total_urls": 0,
                    "urls": [],
                    "invalid": [],
                    "errors": ["Nessuna sitemap trovata per questo sito."]
                })

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

            # 7) AI MODULES (lazy loaded)
            try:
                from app.modules.ai_fix_agents import generate_autofix_report
                ai_autofix = generate_autofix_report(all_errors, scraped)
                yield sse("ai_autofix", ai_autofix)
            except Exception as e:
                logger.error(f"❌ ai_autofix failed: {e}")
                yield sse("ai_autofix", f"AutoFix generation failed: {str(e)[:200]}")

            try:
                from app.modules.ai_schema_agent import generate_schema
                ai_schema = generate_schema(scraped)
                yield sse("ai_schema", ai_schema)
            except Exception as e:
                logger.error(f"❌ ai_schema failed: {e}")
                yield sse("ai_schema", f"Schema generation failed: {str(e)[:200]}")

            try:
                from app.modules.ai_content_expander import expand_content
                ai_expanded = expand_content(scraped, target_keywords)
                yield sse("ai_expanded_content", ai_expanded)
            except Exception as e:
                logger.error(f"❌ ai_expanded_content failed: {e}")
                yield sse("ai_expanded_content", f"Content expansion failed: {str(e)[:200]}")

            try:
                from app.modules.ai_roadmap_agent import generate_roadmap
                ai_roadmap = generate_roadmap(all_errors, scraped)
                print(f"[DEBUG] AI_ROADMAP generated successfully")
                yield sse("ai_roadmap", ai_roadmap)
            except Exception as e:
                print(f"[ERROR] AI_ROADMAP FAILED: {type(e).__name__}: {str(e)}")
                logger.error(f"❌ ai_roadmap failed: {e}", exc_info=True)
                yield sse("ai_roadmap", f"Roadmap generation failed: {str(e)[:200]}")

            # 8) COMPETITOR ANALYSIS (optional - lazy loaded)
            ranking = None
            radar = None
            keyword_analysis = None
            ai_strategy = None
            
            if competitor_url:
                logger.info(f"✅ COMPETITOR ANALYSIS STARTED for {competitor_url}")
                print(f"\n\n✅✅✅ COMPETITOR ANALYSIS STARTED for {competitor_url}\n\n")
                competitor_scraped = smart_scrape_url(competitor_url)
                
                # Arricchisci scraped con dati aggiuntivi per ranking
                enriched_scraped = {
                    **scraped,
                    "performance_score": perf_score,
                    "canonical": technical.get("canonical"),
                    "robots_txt_found": technical.get("robots_txt_found"),
                    "sitemap_found": technical.get("sitemap_found"),
                    "https": url.startswith("https"),
                    "links": scraped.get("links", []),
                }
                
                # Anche per competitor, esegui technical checks
                comp_technical = run_technical_checks(competitor_scraped, competitor_url)
                try:
                    comp_performance = run_performance_engine(competitor_url)
                    comp_perf_score = comp_performance.get("performance_score")
                except Exception:
                    comp_perf_score = None
                
                enriched_competitor = {
                    **competitor_scraped,
                    "performance_score": comp_perf_score,
                    "canonical": comp_technical.get("canonical"),
                    "robots_txt_found": comp_technical.get("robots_txt_found"),
                    "sitemap_found": comp_technical.get("sitemap_found"),
                    "https": competitor_url.startswith("https"),
                    "links": competitor_scraped.get("links", []),
                }
                
                # 8a) Compute scores and ranking
                my_scores = compute_simple_scores(enriched_scraped)
                comp_scores = compute_simple_scores(enriched_competitor)
                ranking = rank_competitor(enriched_scraped, enriched_competitor)
                yield sse("ranking", ranking)
                
                # 8b) Radar
                radar = radar_payload(my_scores, comp_scores)
                yield sse("radar", radar)
                
                # 8c) Keyword analysis (lazy import + parallelized)
                try:
                    from app.modules.competitor.keyword_clustering import cluster_keywords
                    from app.core.async_helpers import parallel_keyword_analysis
                    
                    my_text = " ".join(scraped.get("paragraphs", []) or [])
                    comp_text = " ".join(competitor_scraped.get("paragraphs", []) or [])
                    
                    # Run keyword extraction in parallel via asyncio
                    try:
                        my_keywords, comp_keywords = asyncio.run(
                            parallel_keyword_analysis(my_text, comp_text, top_k=50)
                        )
                    except RuntimeError:
                        # Fallback if asyncio.run() fails (e.g., already in async context)
                        from app.modules.competitor.keyword_extractor import extract_keywords_advanced
                        my_keywords = extract_keywords_advanced(my_text, top_k=50)
                        comp_keywords = extract_keywords_advanced(comp_text, top_k=50)
                    
                    my_kw_set = {kw["kw"] for kw in my_keywords if isinstance(kw, dict)}
                    comp_kw_set = {kw["kw"] for kw in comp_keywords if isinstance(kw, dict)}
                    
                    overlap = list(my_kw_set.intersection(comp_kw_set))
                    gap = list(comp_kw_set - my_kw_set)
                    
                    # 8d) Clustering
                    combined_keywords = list(my_kw_set.union(comp_kw_set))
                    clusters = cluster_keywords(combined_keywords, n_clusters=6)
                    
                    keyword_analysis = {
                        "your_keywords": my_keywords[:20],
                        "competitor_keywords": comp_keywords[:20],
                        "keyword_overlap": overlap[:20],
                        "keyword_gap": gap[:20],
                        "clusters": clusters
                    }
                    yield sse("keyword_analysis", keyword_analysis)
                except Exception as e:
                    logger.error(f"❌ keyword_analysis failed: {e}")
                    yield sse("keyword_analysis", {"error": str(e)[:200]})
                    gap = []
                    overlap = []
                    clusters = []
                
                # 8e) AI Strategy (lazy import)
                try:
                    from app.modules.ai_strategy_agent import generate_strategy
                    compare_payload = {
                        "ranking": ranking,
                        "radar": radar,
                        "keyword_gap": gap,
                        "keyword_overlap": overlap,
                        "clusters": clusters
                    }
                    
                    ai_strategy = generate_strategy(
                        scan=scraped,
                        competitor=competitor_scraped,
                        compare=compare_payload
                    )
                    yield sse("ai_strategy", ai_strategy)
                except Exception as e:
                    logger.error(f"❌ ai_strategy failed: {e}")
                    yield sse("ai_strategy", f"Strategy generation failed: {str(e)[:200]}")

            # 9) DONE
            yield sse("done", {"status": "completed"})
            logger.info("✅ SCAN-FULL COMPLETED")

        except Exception as e:
            logger.error(f"❌ ERROR in scan_full_stream: {str(e)}", exc_info=True)
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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
