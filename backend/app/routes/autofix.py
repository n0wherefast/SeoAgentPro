from fastapi import APIRouter
from app.modules.ai_fix_agents import generate_autofix_report

router = APIRouter()
# COMMENTATA IN MAIN.PY E NON USATA AL MOMENTO
@router.post("/autofix")
async def autofix(data: dict):
    errors = data.get("errors", [])
    page_data = data.get("page_data", {})

    report = generate_autofix_report(errors, page_data)

    return {
        "autofix": report
    }