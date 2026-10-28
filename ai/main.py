from pathlib import Path
import shutil
import sys
import tempfile

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from services.embedding_service import embed_text
from services.video_pipeline import analyze_video_file
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


class AnalyzeResponse(BaseModel):
    title: str
    summary: str
    categories: list[str]
    keywords: list[str]
    entities: list[str]
    structured: dict = Field(default_factory=dict)


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
    try:
        return EmbedResponse(**embed_text(request.text))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"임베딩 생성 실패: {exc}",
        ) from exc


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_url(request: AnalyzeRequest):
    source_url = request.sourceUrl.strip()
    url = source_url.lower()

    if is_instagram_reel_url(source_url):
        with tempfile.TemporaryDirectory(
            prefix="saveon-instagram-"
        ) as temp_dir:
            try:
                media = download_instagram_reel(
                    source_url,
                    Path(temp_dir),
                )

                result = analyze_video_file(
                    media.path,
                    audio_path=media.audio_path,
                    source_title=media.title,
                    source_description=media.description,
                    source_channel=media.channel,
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
                media = download_youtube_video(
                    source_url,
                    Path(temp_dir),
                )
                result = analyze_video_file(
                    media.path,
                    audio_path=media.audio_path,
                    source_title=media.title,
                    source_description=media.description,
                    source_channel=media.channel,
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

    with tempfile.TemporaryDirectory(prefix="saveon-") as temp_dir:
        video_path = Path(temp_dir) / f"input{suffix}"

        try:
            with video_path.open("wb") as output:
                shutil.copyfileobj(file.file, output)

            result = analyze_video_file(video_path)
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

    with tempfile.TemporaryDirectory(prefix="saveon-") as temp_dir:
        video_path = Path(temp_dir) / f"input{suffix}"

        try:
            video_path.write_bytes(data)

            print(
                f"[RAW VIDEO] 수신 완료: "
                f"{filename} / {len(data)} bytes"
            )

            result = analyze_video_file(video_path)

            return AnalyzeResponse(**result)

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"영상 분석 실패: {exc}",
            ) from exc
