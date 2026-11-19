from pathlib import Path
from typing import Literal
import hmac
import os
import shutil
import sys
import tempfile

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from services.embedding_service import embed_text
from services.llm_postprocessor import default_prompt_variant, postprocess_with_llm
from services.summary_review import review_summary, suggest_examples
from services.video_pipeline import analyze_video_file
from services.telemetry import pipeline_step, trace_session
from services.analysis_progress import progress_scope, get_progress
from services.instagram_source import (
    InstagramDownloadError,
    InvalidInstagramUrlError,
    download_instagram_reel,
    is_instagram_reel_url,
)
from services.youtube_source import (
    InvalidYouTubeUrlError,
    YouTubeDownloadError,
    download_youtube_video,
    is_youtube_url,
)


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


app = FastAPI(
    title="SaveOn AI Server",
    version="2.2.0",
)


class AnalyzeRequest(BaseModel):
    sourceUrl: str
    thumbnailRequested: bool = False  # rights confirmed by the user
    promptVariant: Literal["baseline", "few_shot_v1", "structured_v2"] = Field(default_factory=default_prompt_variant)


class AnalyzeResponse(BaseModel):
    title: str
    summary: str
    categories: list[str]
    keywords: list[str]
    entities: list[str]
    structured: dict = Field(default_factory=dict)
    thumbnailBase64: str | None = None  # optional 384px JPEG only for opted-in Reels


class RevisionEvidence(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)
    modality: Literal["STT", "OCR"]
    timeMs: int | None = Field(default=None, ge=0)
    startMs: int | None = Field(default=None, ge=0)
    endMs: int | None = Field(default=None, ge=0)


class SummaryRevisionRequest(BaseModel):
    sourceTitle: str = Field(default="", max_length=300)
    evidence: list[RevisionEvidence] = Field(min_length=1, max_length=200)
    previousSummary: str = Field(max_length=4000)
    feedback: str = Field(default="", max_length=2000)
    desiredSummary: str = Field(default="", max_length=4000)


def require_evaluation_token(x_evaluation_token: str):
    token = os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip()
    if not token or not hmac.compare_digest(token.encode(), x_evaluation_token.encode()):
        raise HTTPException(status_code=403)


class SummaryReviewRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    evidence: list[RevisionEvidence] = Field(min_length=1, max_length=200)
    goldReference: str = Field(default="", max_length=8000)
    goldStatus: str = Field(default="DRAFT", max_length=50)


class PromptTrainingReview(BaseModel):
    itemId: str = Field(min_length=1, max_length=80)
    findings: list[dict[str, str]] = Field(max_length=6)


class PromptSuggestionRequest(BaseModel):
    reviews: list[PromptTrainingReview] = Field(min_length=2, max_length=12)


@app.post("/internal/suggest-prompt-examples")
def propose_prompt_examples(payload: PromptSuggestionRequest, x_evaluation_token: str = Header(default="")):
    require_evaluation_token(x_evaluation_token)
    return suggest_examples([review.model_dump() for review in payload.reviews])


class PromptTrialExample(BaseModel):
    exampleInput: str = Field(min_length=1, max_length=600)
    exampleOutput: str = Field(min_length=1, max_length=600)


class PromptTrialRequest(BaseModel):
    sourceTitle: str = Field(default="", max_length=300)
    evidence: list[RevisionEvidence] = Field(min_length=1, max_length=200)
    examples: list[PromptTrialExample] = Field(default_factory=list, max_length=3)


@app.post("/internal/replay-prompt", response_model=AnalyzeResponse)
def replay_prompt(payload: PromptTrialRequest, x_evaluation_token: str = Header(default="")):
    require_evaluation_token(x_evaluation_token)
    units = [unit.model_dump(exclude_none=True) for unit in payload.evidence]
    result = postprocess_with_llm(
        " ".join(unit.text for unit in payload.evidence if unit.modality == "STT"),
        [unit.text for unit in payload.evidence if unit.modality == "OCR"],
        [], evidence_units=units, source_title=payload.sourceTitle,
        candidate_examples=[example.model_dump() for example in payload.examples],
    )
    result["structured"].update(videoEvidence=units, verificationStatus="NOT_RUN")
    return result


@app.post("/internal/review-summary")
def create_summary_review(payload: SummaryReviewRequest, x_evaluation_token: str = Header(default="")):
    require_evaluation_token(x_evaluation_token)
    try:
        return review_summary(payload.summary, [unit.model_dump(exclude_none=True) for unit in payload.evidence],
                              payload.goldReference, payload.goldStatus)
    except Exception as exc:
        if getattr(exc, "code", None) == 429:
            raise HTTPException(429, "Gemini 호출 한도에 도달했습니다.") from exc
        raise HTTPException(502, "Gemini 평가 결과를 가져오지 못했습니다.") from exc


@app.post("/internal/revise-summary", response_model=AnalyzeResponse)
def revise_summary(payload: SummaryRevisionRequest, x_evaluation_token: str = Header(default="")):
    require_evaluation_token(x_evaluation_token)
    if not (payload.feedback.strip() or payload.desiredSummary.strip()):
        raise HTTPException(status_code=422, detail="검토 의견이나 원하는 요약 예시를 입력해 주세요.")
    units = [unit.model_dump(exclude_none=True) for unit in payload.evidence]
    result = postprocess_with_llm(
        " ".join(unit.text for unit in payload.evidence if unit.modality == "STT"),
        [unit.text for unit in payload.evidence if unit.modality == "OCR"],
        [], evidence_units=units, source_title=payload.sourceTitle, prompt_variant="few_shot_v1",
        revision_guidance={"previousSummary": payload.previousSummary,
                           "reviewNote": payload.feedback, "desiredOutputExample": payload.desiredSummary},
    )
    structured = result["structured"]
    if not (structured.get("targets") or structured.get("globalSteps")):
        raise HTTPException(status_code=422, detail="근거에 연결된 요약을 생성하지 못했습니다.")
    structured.update(videoEvidence=units, verificationStatus="NOT_RUN", promptVariant="review_guided")
    return result


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    model: str
    dimensions: int
    vector: list[float]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "saveon-ai",
        "version": "2.2.0",
    }


@app.post("/embed", response_model=EmbedResponse)
def create_embedding(request: EmbedRequest):
    with trace_session(
        platform="INTERNAL",
        source_url="embedding-request",
    ):
        try:
            with pipeline_step(
                "semantic-embedding",
                kind="TOOL",
                model="gemini-embedding-2",
                input_summary={"textLength": len(request.text)},
            ) as step:
                result = EmbedResponse(**embed_text(request.text))
                step.set_output({"dimensions": result.dimensions})
                return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"임베딩 생성 실패: {exc}",
            ) from exc


@app.get("/progress/{content_id}")
def get_live_analysis_progress(content_id: int):
    return get_progress(content_id)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_url(
    request: AnalyzeRequest,
    x_saveon_content_id: str | None = Header(default=None),
):
    source_url = request.sourceUrl.strip()
    platform = (
        "INSTAGRAM"
        if is_instagram_reel_url(source_url)
        else "YOUTUBE"
        if is_youtube_url(source_url)
        else "WEB"
    )

    # save:on TRUE_PROGRESS_V1: request id propagated from Spring for live stages.
    with progress_scope(x_saveon_content_id):
        with trace_session(
            platform=platform,
            source_url=source_url,
        ):
            return _analyze_source_url(source_url, thumbnail_requested=request.thumbnailRequested, prompt_variant=request.promptVariant)


def _analyze_source_url(source_url: str, *, thumbnail_requested: bool = False, prompt_variant: str = "baseline"):
    url = source_url.lower()

    if is_instagram_reel_url(source_url):
        with tempfile.TemporaryDirectory(
            prefix="saveon-instagram-"
        ) as temp_dir:
            try:
                with pipeline_step(
                    "source-download",
                    kind="TOOL",
                    input_summary={"platform": "INSTAGRAM"},
                ) as step:
                    media = download_instagram_reel(
                        source_url,
                        Path(temp_dir),
                    )
                    step.set_output({
                        "title": media.title,
                        "hasAudio": media.audio_path is not None,
                    })

                result = analyze_video_file(
                    media.path,
                    audio_path=media.audio_path,
                    source_title=media.title,
                    source_description=media.description,
                    source_channel=media.channel,
                    thumbnail_requested=thumbnail_requested,
                    prompt_variant=prompt_variant,
                )

                return AnalyzeResponse(**result)

            except InvalidInstagramUrlError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=str(exc),
                ) from exc

            except InstagramDownloadError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc

            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Instagram 릴스 분석 실패: {exc}",
                ) from exc

    if "instagram.com" in url:
        raise HTTPException(
            status_code=400,
            detail="현재는 Instagram Reel URL만 지원합니다.",
        )

    if is_youtube_url(source_url):
        with tempfile.TemporaryDirectory(
            prefix="saveon-youtube-"
        ) as temp_dir:
            try:
                with pipeline_step(
                    "source-download",
                    kind="TOOL",
                    input_summary={"platform": "YOUTUBE"},
                ) as step:
                    media = download_youtube_video(
                        source_url,
                        Path(temp_dir),
                    )
                    step.set_output({
                        "title": media.title,
                        "hasAudio": media.audio_path is not None,
                    })
                result = analyze_video_file(
                    media.path,
                    audio_path=media.audio_path,
                    source_title=media.title,
                    source_description=media.description,
                    source_channel=media.channel,
                    prompt_variant=prompt_variant,
                )
                return AnalyzeResponse(**result)
            except InvalidYouTubeUrlError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=str(exc),
                ) from exc
            except YouTubeDownloadError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"YouTube 영상 분석 실패: {exc}",
                ) from exc

    return AnalyzeResponse(
        title="웹 콘텐츠",
        summary="웹 URL이 저장되었습니다.",
        categories=["Web"],
        keywords=["웹 콘텐츠"],
        entities=[],
        structured={},
    )


@app.post("/analyze-video", response_model=AnalyzeResponse)
async def analyze_video(file: UploadFile = File(...)):
    filename = file.filename or "upload.mp4"
    suffix = Path(filename).suffix or ".mp4"

    with trace_session(platform="UPLOAD", source_url=filename):
        with tempfile.TemporaryDirectory(prefix="saveon-") as temp_dir:
            video_path = Path(temp_dir) / f"input{suffix}"

            try:
                with pipeline_step(
                    "upload-save",
                    kind="TOOL",
                ) as step:
                    with video_path.open("wb") as output:
                        shutil.copyfileobj(file.file, output)
                    step.set_output({"fileType": suffix.lower()})

                result = analyze_video_file(video_path, prompt_variant=default_prompt_variant())
                return AnalyzeResponse(**result)

            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"영상 분석 실패: {exc}",
                ) from exc


@app.post("/analyze-video-raw", response_model=AnalyzeResponse)
async def analyze_video_raw(
    request: Request,
    x_filename: str | None = Header(default=None),
):
    data = await request.body()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="영상 바이트가 비어 있습니다.",
        )

    filename = x_filename or "upload.mp4"
    suffix = Path(filename).suffix or ".mp4"

    with trace_session(platform="UPLOAD", source_url=filename):
        with tempfile.TemporaryDirectory(prefix="saveon-") as temp_dir:
            video_path = Path(temp_dir) / f"input{suffix}"

            try:
                with pipeline_step(
                    "upload-save",
                    kind="TOOL",
                    input_summary={"byteCount": len(data)},
                ) as step:
                    video_path.write_bytes(data)
                    step.set_output({"fileType": suffix.lower()})

                print(
                    f"[RAW VIDEO] 수신 완료: "
                    f"{filename} / {len(data)} bytes"
                )

                result = analyze_video_file(video_path, prompt_variant=default_prompt_variant())

                return AnalyzeResponse(**result)

            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"영상 분석 실패: {exc}",
                ) from exc

# save:on TRUE_PROGRESS_V1
# SAVEON_INSTAGRAM_THUMBNAIL_V1
