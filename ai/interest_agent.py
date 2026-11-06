from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from services.interest_synthesis import (
    GEMINI_MODEL,
    InterestSynthesisRequest,
    InterestSynthesisResponse,
    synthesize_interest,
)


app = FastAPI(
    title="SaveOn Interest Synthesis Agent",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "saveon-interest-agent",
        "version": "1.0.0",
        "model": GEMINI_MODEL,
    }


@app.post(
    "/synthesize",
    response_model=InterestSynthesisResponse,
)
def synthesize(
    request: InterestSynthesisRequest,
    response: Response,
):
    if request.count < 2:
        raise HTTPException(
            status_code=400,
            detail="관심 통합에는 2개 이상의 연결 콘텐츠가 필요합니다.",
        )

    try:
        result, cache_hit = synthesize_interest(request)
        response.headers["X-SaveOn-Agent"] = "interest-synthesis"
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
            detail=f"Interest Synthesis Agent 실패: {exc}",
        ) from exc
