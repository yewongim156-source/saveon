from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from urllib.parse import urlsplit


# YouTube reviews are often a little longer than Shorts/Reels. Save:on still
# rejects very long videos by default, but the test/review use case can now
# handle videos up to 20 minutes. Override with YOUTUBE_MAX_DURATION_SECONDS.
# "720p" must also cover vertical Shorts, whose 720p stream is 720x1280. A plain
# height<=720 filter silently picked the 360x640 stream, which is too small for
# OCR to read overlay text such as product cards.
_RESOLUTION_LIMIT = "[height<=1280][width<=1280]"

DEFAULT_MAX_DURATION_SECONDS = 20 * 60
DEFAULT_MAX_FILE_SIZE_MB = 150
MIN_DOWNLOADED_FILE_BYTES = 1024


class YouTubeSourceError(RuntimeError):
    """Base error for a YouTube source that cannot be analyzed."""


class InvalidYouTubeUrlError(YouTubeSourceError):
    """Raised when the input is not a supported YouTube video URL."""


class YouTubeDownloadError(YouTubeSourceError):
    """Raised when video metadata or media cannot be acquired."""


@dataclass(frozen=True)
class YouTubeMedia:
    path: Path
    audio_path: Path | None
    video_id: str
    title: str
    description: str
    channel: str
    duration_seconds: int | None
    webpage_url: str


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False

    hostname = (parsed.hostname or "").lower().rstrip(".")
    return (
        hostname == "youtu.be"
        or hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
    )


def _positive_int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise YouTubeSourceError(
            f"{name} 환경 변수는 정수여야 합니다."
        ) from exc

    if value <= 0:
        raise YouTubeSourceError(
            f"{name} 환경 변수는 0보다 커야 합니다."
        )
    return value


def _validate_metadata(info: dict) -> None:
    if info.get("_type") in {"playlist", "multi_video"}:
        raise InvalidYouTubeUrlError(
            "재생목록이 아닌 단일 YouTube 영상 URL을 입력해 주세요."
        )

    if info.get("is_live") or info.get("live_status") in {
        "is_live",
        "is_upcoming",
        "post_live",
    }:
        raise InvalidYouTubeUrlError(
            "라이브 또는 아직 처리 중인 영상은 분석할 수 없습니다."
        )

    duration = info.get("duration")
    max_duration = _positive_int_from_env(
        "YOUTUBE_MAX_DURATION_SECONDS",
        DEFAULT_MAX_DURATION_SECONDS,
    )

    if isinstance(duration, (int, float)) and duration > max_duration:
        minutes = max_duration // 60
        raise InvalidYouTubeUrlError(
            f"현재는 {minutes}분 이하 YouTube 영상만 분석할 수 있습니다. "
            "필요하면 YOUTUBE_MAX_DURATION_SECONDS 환경 변수로 조정할 수 있어요."
        )


def _safe_video_id(info: dict) -> str:
    raw_id = str(info.get("id") or "video")
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", raw_id)
    return cleaned or "video"


def _valid_media_file(candidate: Path) -> bool:
    try:
        return (
            candidate.is_file()
            and candidate.suffix not in {".part", ".ytdl"}
            and candidate.stat().st_size >= MIN_DOWNLOADED_FILE_BYTES
        )
    except OSError:
        return False


def _find_downloaded_path(
    output_dir: Path,
    info: dict,
    prepared_filename: str | None,
    filename_prefix: str,
) -> Path:
    candidates: list[Path] = []

    if prepared_filename:
        candidates.append(Path(prepared_filename))

    for item in info.get("requested_downloads") or []:
        filepath = item.get("filepath")
        if filepath:
            candidates.append(Path(filepath))

    candidates.extend(output_dir.glob(f"{filename_prefix}.*"))

    for candidate in candidates:
        if _valid_media_file(candidate):
            return candidate

    existing = [
        f"{item.name}:{item.stat().st_size}"
        for item in output_dir.glob("*")
        if item.is_file()
    ]
    raise YouTubeDownloadError(
        "다운로드 후 유효한 영상 파일을 찾지 못했습니다. "
        f"temp files={existing[:8]}"
    )


def _has_stream(
    metadata: dict,
    *,
    needs_video: bool,
    needs_audio: bool,
) -> bool:
    formats = metadata.get("formats")
    if not isinstance(formats, list):
        return True

    for item in formats:
        has_video = item.get("vcodec") not in {None, "none"}
        has_audio = item.get("acodec") not in {None, "none"}
        if (not needs_video or has_video) and (not needs_audio or has_audio):
            return True
    return False


def _download_stream(
    YoutubeDL,
    common_options: dict,
    url: str,
    output_dir: Path,
    *,
    format_selector: str,
    filename_suffix: str,
    max_file_size: int,
) -> tuple[Path, dict]:
    options = {
        **common_options,
        "format": format_selector,
        "outtmpl": str(
            output_dir
            / f"youtube-%(id)s-{filename_suffix}.%(ext)s"
        ),
        "max_filesize": max_file_size,
        "overwrites": True,
        "restrictfilenames": True,
    }

    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        if not isinstance(info, dict):
            raise YouTubeDownloadError(
                "YouTube 미디어 스트림을 다운로드할 수 없습니다."
            )
        prepared_filename = downloader.prepare_filename(info)

    filename_prefix = (
        f"youtube-{_safe_video_id(info)}-{filename_suffix}"
    )
    path = _find_downloaded_path(
        output_dir,
        info,
        prepared_filename,
        filename_prefix,
    )

    print(
        "[YOUTUBE] stream ready: "
        f"{path.name} / {path.stat().st_size} bytes"
    )
    return path, info


def download_youtube_video(
    url: str,
    output_dir: Path,
) -> YouTubeMedia:
    normalized_url = url.strip()
    if not is_youtube_url(normalized_url):
        raise InvalidYouTubeUrlError(
            "지원하는 YouTube 또는 youtu.be 영상 URL이 아닙니다."
        )

    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise YouTubeDownloadError(
            "yt-dlp가 설치되어 있지 않습니다. requirements.txt를 설치해 주세요."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    max_file_size = _positive_int_from_env(
        "YOUTUBE_MAX_FILE_SIZE_MB",
        DEFAULT_MAX_FILE_SIZE_MB,
    ) * 1024 * 1024

    common_options = {
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "cachedir": False,
    }

    try:
        with YoutubeDL(common_options) as metadata_loader:
            metadata = metadata_loader.extract_info(
                normalized_url,
                download=False,
            )

        if not isinstance(metadata, dict):
            raise YouTubeDownloadError(
                "YouTube 영상 정보를 확인할 수 없습니다."
            )
        _validate_metadata(metadata)

        duration = metadata.get("duration")
        print(
            "[YOUTUBE] metadata ok: "
            f"id={_safe_video_id(metadata)} duration={duration}s"
        )

        audio_path: Path | None = None

        if _has_stream(
            metadata,
            needs_video=True,
            needs_audio=True,
        ):
            video_path, downloaded = _download_stream(
                YoutubeDL,
                common_options,
                normalized_url,
                output_dir,
                format_selector=(
                    f"best[ext=mp4]{_RESOLUTION_LIMIT}[acodec!=none]/"
                    f"best{_RESOLUTION_LIMIT}[acodec!=none]/best"
                ),
                filename_suffix="media",
                max_file_size=max_file_size,
            )
            audio_path = video_path
        else:
            video_path, downloaded = _download_stream(
                YoutubeDL,
                common_options,
                normalized_url,
                output_dir,
                format_selector=(
                    f"bestvideo[ext=mp4]{_RESOLUTION_LIMIT}/"
                    f"bestvideo{_RESOLUTION_LIMIT}/bestvideo"
                ),
                filename_suffix="video",
                max_file_size=max_file_size,
            )

            if _has_stream(
                metadata,
                needs_video=False,
                needs_audio=True,
            ):
                try:
                    audio_path, _ = _download_stream(
                        YoutubeDL,
                        common_options,
                        normalized_url,
                        output_dir,
                        format_selector="bestaudio[ext=m4a]/bestaudio",
                        filename_suffix="audio",
                        max_file_size=max_file_size,
                    )
                except DownloadError as exc:
                    print(
                        "[YOUTUBE] 오디오 스트림 확보 실패 - "
                        f"화면 분석만 진행: {exc}"
                    )

        if not _valid_media_file(video_path):
            raise YouTubeDownloadError(
                "YouTube 영상 파일이 비어 있거나 유효하지 않습니다."
            )

        if audio_path is not None and not _valid_media_file(audio_path):
            print(
                "[YOUTUBE] 오디오 파일이 비어 있어 영상 파일로 STT를 시도합니다."
            )
            audio_path = video_path

        total_size = video_path.stat().st_size
        if audio_path is not None and audio_path != video_path:
            total_size += audio_path.stat().st_size

        if total_size > max_file_size:
            video_path.unlink(missing_ok=True)
            if audio_path is not None and audio_path != video_path:
                audio_path.unlink(missing_ok=True)
            raise InvalidYouTubeUrlError(
                f"영상 파일은 {max_file_size // (1024 * 1024)}MB 이하여야 합니다."
            )

    except InvalidYouTubeUrlError:
        raise
    except DownloadError as exc:
        raise YouTubeDownloadError(
            "YouTube 다운로드에 실패했습니다. "
            "공개 상태·연령 제한·로그인 필요·지역 제한 여부를 확인해 주세요. "
            f"원인: {exc}"
        ) from exc
    except YouTubeSourceError:
        raise
    except Exception as exc:
        raise YouTubeDownloadError(
            f"YouTube 영상 확보 중 오류가 발생했습니다: {exc}"
        ) from exc

    return YouTubeMedia(
        path=video_path,
        audio_path=audio_path,
        video_id=_safe_video_id(downloaded),
        title=str(downloaded.get("title") or metadata.get("title") or ""),
        description=str(
            downloaded.get("description")
            or metadata.get("description")
            or ""
        ),
        channel=str(
            downloaded.get("channel")
            or downloaded.get("uploader")
            or metadata.get("channel")
            or metadata.get("uploader")
            or ""
        ),
        duration_seconds=(
            int(downloaded["duration"])
            if isinstance(downloaded.get("duration"), (int, float))
            else None
        ),
        webpage_url=str(
            downloaded.get("webpage_url")
            or metadata.get("webpage_url")
            or normalized_url
        ),
    )
