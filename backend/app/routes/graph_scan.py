"""
✅ ACTIVE: Graph Scan Endpoint - Advanced SEO audit workflow (PRIMARY for graph-scan)
POST /graph-scan endpoint with comprehensive report generation
GET /graph-scan/stream for SSE streaming results
"""

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from app.modules.graph_agent import GraphAuditOrchestrator
from app.modules.seo_technical import analyze_sitemap
from app.utils.validators import validate_url

router = APIRouter()


class GraphScanRequest(BaseModel):
    url: str
    competitor_count: int = 3
    focus: str = "general"

    @field_validator("url")
    @classmethod
    def validate_scan_url(cls, v: str) -> str:
        return validate_url(v)



@router.post("/agent-scan")
async def agent_scan(data: GraphScanRequest):
    """
    Advanced SEO audit using orchestrated workflow.
    
    Performs:
    1. Web scraping (HTTPX + Playwright fallback)
    2. SEO analysis (20+ checks)
    3. Security analysis (API key detection)
    4. Competitor research
    5. AI-powered fixes generation
    6. Comprehensive Markdown report
    
    Returns a complete audit report with all findings and recommendations.
    """
    try:
        # Create orchestrator and run audit
        orchestrator = GraphAuditOrchestrator()
        final_state = orchestrator.run_audit(
            url=data.url,
            competitor_count=data.competitor_count,
            focus=data.focus
        )

        # Analisi sitemap se presente in seo_data
        seo_data = final_state.get("seo_data") or {}
        sitemap_url = seo_data.get("sitemap_url")
        sitemap_analysis = analyze_sitemap(sitemap_url) if sitemap_url else None
        return {
            "url": final_state.get("url"),
            "seo_score": final_state.get("seo_score"),
            "seo_data": seo_data,
            "sitemap_analysis": sitemap_analysis,
            "issues": final_state.get("issues"),
            "fixes": final_state.get("fixes"),
            "competitors": final_state.get("competitors"),
            "report": final_state.get("final_report_md")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph audit failed: {str(e)}")


@router.get("/agent-scan/stream")
# @router.get("/graph-scan/stream")
def agent_scan_stream(url: str, competitor_count: int = 3, focus: str = "general") -> StreamingResponse:
    orchestrator = GraphAuditOrchestrator()
    generator = orchestrator.run_audit_stream(url=url, competitor_count=competitor_count, focus=focus)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


