from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from services.action_planner import (
    GEMINI_MODEL,
    ActionPlanRequest,
    ActionPlanResponse,
    plan_actions,
)


app = FastAPI(
    title="SaveOn Action Agent",
    version="1.6.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "saveon-action-agent",
        "version": "1.6.0",
        "model": GEMINI_MODEL,
        "supportedContexts": [
            "SINGLE_CONTENT",
            "CONTENT_BUNDLE",
        ],
        "supportedActions": [
            "MAP_SEARCH",
            "WEB_SEARCH",
            "COMPARE_SEARCH",
            "CALENDAR_ADD",
            "CHECKLIST_CREATE",
        ],
    }


@app.post(
    "/plan",
    response_model=ActionPlanResponse,
)
def plan(
    request: ActionPlanRequest,
    response: Response,
):
    try:
        result, cache_hit = plan_actions(request)
        response.headers["X-SaveOn-Agent"] = "action-agent"
        response.headers["X-SaveOn-Cache"] = (
            "HIT" if cache_hit else "MISS"
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Action Agent 실패: {exc}",
        ) from exc
