from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from app.modules.scraper import scrape_url
from app.modules.seo_detection_unified import detect_seo_issues_unified
from app.modules.seo_technical import run_technical_checks, analyze_sitemap
from app.modules.competitor.lighthouse_client import run_performance_engine
from app.modules.authority_engine import run_authority_engine
from app.modules.seo_rules import SEOScoringEngine
from app.modules.competitor.ranking import rank_competitor, compute_simple_scores
from app.modules.competitor.radar import radar_payload
from app.modules.pdf_report import generate_pdf_report
import os
import json
import time
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter()

def analyze_keyword_presence(scraped: dict, keywords: list) -> dict:
    results = {}
    for keyword in keywords:
        results[keyword] = {
            "found": False,
            "position": None,
            "content": ""
        }
    for content in scraped["content"]:
        for keyword in keywords:
            if keyword.lower() in content.lower():
                results[keyword]["found"] = True
                results[keyword]["position"] = content.find(keyword.lower())
                results[keyword]["content"] = content
    return {
        "keywords": results,
        "total_keywords": len(keywords),
        "keywords_found": sum(1 for result in results.values() if result["found"]),
        "coverage_percent": round(sum(1 for result in results.values() if result["found"]) / len(keywords) * 100) if keywords else 0,
        "summary": f"{sum(1 for result in results.values() if result['found'])}/{len(keywords)} keywords trovate nel contenuto"
    }

@router.options("/agent-scan/stream")
async def options_agent_scan():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

@router.get("/agent-scan/stream")
async def agent_scan_stream(
    request: Request,
    url: str,
    competitor_url: str | None = None,
    keywords: str | None = None
):
    target_keywords = [k.strip() for k in (keywords or "").split(",") if k.strip()]
    async def event_generator():
        try:
            logger.info(f"🔍 AGENT-SCAN START: url={url}, competitor_url={competitor_url}, keywords={target_keywords}")
            print(f"\n\n🔍🔍🔍 AGENT-SCAN START: url={url}, competitor_url={competitor_url}, keywords={target_keywords}\n\n")
            scraped = scrape_url(url)
            yield sse("scrape", scraped)
            onpage_errors = detect_seo_issues_unified(scraped)
            yield sse("onpage_errors", onpage_errors)
            if target_keywords:
                keyword_presence = analyze_keyword_presence(scraped, target_keywords)
                yield sse("keyword_analysis", keyword_presence)
            technical = run_technical_checks(scraped, url)
            technical_errors = technical["technical_errors"]
            yield sse("technical", technical)
            sitemap_url = technical.get("sitemap_url")
            if sitemap_url:
                sitemap_data = analyze_sitemap(sitemap_url)
                yield sse("sitemap_analysis", sitemap_data)
            else:
                # Forza invio evento anche se non trovata
                yield sse("sitemap_analysis", {
                    "sitemap_url": None,
                    "is_index": False,
                    "total_urls": 0,
                    "urls": [],
                    "invalid": [],
                    "errors": ["Nessuna sitemap trovata per questo sito."]
                })
            # ...existing code for performance, authority, etc...
        except Exception as e:
            logger.error(f"❌ ERROR in agent_scan_stream: {str(e)}", exc_info=True)
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

def sse(event: str, data):
    json_str = json.dumps(data)
    return f"event: {event}\ndata: {json_str}\n\n"
