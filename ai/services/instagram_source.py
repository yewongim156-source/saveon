from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from urllib.parse import urlsplit


DEFAULT_MAX_DURATION_SECONDS = 10 * 60
DEFAULT_MAX_FILE_SIZE_MB = 150


class InstagramSourceError(RuntimeError):
    """Base error for an Instagram Reel source that cannot be analyzed."""


class InvalidInstagramUrlError(InstagramSourceError):
    """Raised when the input is not a supported Instagram Reel URL."""


class InstagramDownloadError(InstagramSourceError):
    """Raised when Reel metadata or media cannot be acquired."""


@dataclass(frozen=True)
class InstagramMedia:
    path: Path
    audio_path: Path | None
    shortcode: str
    title: str
    description: str
    channel: str
    duration_seconds: int | None
    webpage_url: str


def is_instagram_reel_url(url: str) -> bool:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    if parsed.username or parsed.password:
        return False

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname not in {"instagram.com", "www.instagram.com"}:
        return False

    parts = [part for part in parsed.path.split("/") if part]
    return (
        len(parts) >= 2
        and parts[0].lower() in {"reel", "reels"}
        and bool(parts[1].strip())
    )


def _positive_int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise InstagramSourceError(
            f"{name} 환경 변수는 정수여야 합니다."
        ) from exc

    if value <= 0:
        raise InstagramSourceError(
            f"{name} 환경 변수는 0보다 커야 합니다."
        )

    return value


def _validate_metadata(info: dict) -> None:
    if info.get("_type") in {"playlist", "multi_video"}:
        raise InvalidInstagramUrlError(
            "단일 Instagram Reel URL만 분석할 수 있습니다."
        )

    duration = info.get("duration")
    max_duration = _positive_int_from_env(
        "INSTAGRAM_MAX_DURATION_SECONDS",
        DEFAULT_MAX_DURATION_SECONDS,
    )

    if (
        isinstance(duration, (int, float))
        and duration > max_duration
    ):
        raise InvalidInstagramUrlError(
            f"{max_duration}초 이하 릴스만 분석할 수 있습니다."
        )


def _safe_shortcode(info: dict) -> str:
    raw_id = str(
        info.get("display_id")
        or info.get("id")
        or "reel"
    )
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", raw_id)
    return cleaned or "reel"


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

    candidates.extend(
        output_dir.glob(f"{filename_prefix}.*")
    )

    for candidate in candidates:
        if (
            candidate.is_file()
            and candidate.suffix not in {".part", ".ytdl"}
        ):
            return candidate

    raise InstagramDownloadError(
        "다운로드는 완료됐지만 분석할 릴스 파일을 찾지 못했습니다."
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

        if (
            (not needs_video or has_video)
            and (not needs_audio or has_audio)
        ):
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
            / f"instagram-%(id)s-{filename_suffix}.%(ext)s"
        ),
        "max_filesize": max_file_size,
        "overwrites": True,
        "restrictfilenames": True,
    }

    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(
            url,
            download=True,
        )

        if not isinstance(info, dict):
            raise InstagramDownloadError(
                "Instagram 릴스 미디어를 다운로드할 수 없습니다."
            )

        prepared_filename = downloader.prepare_filename(
            info
        )

    filename_prefix = (
        f"instagram-{_safe_shortcode(info)}-{filename_suffix}"
    )

    return (
        _find_downloaded_path(
            output_dir,
            info,
            prepared_filename,
            filename_prefix,
        ),
        info,
    )


def download_instagram_reel(
    url: str,
    output_dir: Path,
) -> InstagramMedia:
    """
    Download one publicly accessible Instagram Reel.

    No Instagram username, password, or session cookie is requested.
    Reels that require login or are private are rejected.
    """
    normalized_url = url.strip()

    if not is_instagram_reel_url(normalized_url):
        raise InvalidInstagramUrlError(
            "지원하는 Instagram Reel URL이 아닙니다."
        )

    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise InstagramDownloadError(
            "yt-dlp가 설치되어 있지 않습니다. "
            "requirements.txt를 설치해 주세요."
        ) from exc

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    max_file_size = _positive_int_from_env(
        "INSTAGRAM_MAX_FILE_SIZE_MB",
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
            raise InstagramDownloadError(
                "Instagram 릴스 정보를 확인할 수 없습니다."
            )

        _validate_metadata(metadata)

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
                    "best[ext=mp4][height<=720][acodec!=none]/"
                    "best[height<=720][acodec!=none]/best"
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
                    "bestvideo[ext=mp4][height<=720]/"
                    "bestvideo[height<=720]/bestvideo"
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
                        format_selector=(
                            "bestaudio[ext=m4a]/bestaudio"
                        ),
                        filename_suffix="audio",
                        max_file_size=max_file_size,
                    )
                except DownloadError as exc:
                    print(
                        "[INSTAGRAM] 오디오 스트림 확보 실패 - "
                        f"화면 분석만 진행: {exc}"
                    )

        total_size = video_path.stat().st_size

        if (
            audio_path is not None
            and audio_path != video_path
        ):
            total_size += audio_path.stat().st_size

        if total_size > max_file_size:
            video_path.unlink(missing_ok=True)

            if (
                audio_path is not None
                and audio_path != video_path
            ):
                audio_path.unlink(missing_ok=True)

            raise InvalidInstagramUrlError(
                "릴스 파일은 "
                f"{max_file_size // (1024 * 1024)}MB "
                "이하여야 합니다."
            )

    except InvalidInstagramUrlError:
        raise
    except DownloadError as exc:
        raise InstagramDownloadError(
            "공개 릴스를 가져오지 못했습니다. "
            "비공개·로그인 필요·연령/지역 제한 콘텐츠는 "
            "URL만으로 분석할 수 없습니다."
        ) from exc
    except InstagramSourceError:
        raise
    except Exception as exc:
        raise InstagramDownloadError(
            "Instagram 릴스 확보 중 오류가 발생했습니다: "
            f"{exc}"
        ) from exc

    title = str(
        downloaded.get("title")
        or metadata.get("title")
        or ""
    )

    description = str(
        downloaded.get("description")
        or metadata.get("description")
        or ""
    )

    channel = str(
        downloaded.get("uploader")
        or downloaded.get("channel")
        or metadata.get("uploader")
        or metadata.get("channel")
        or ""
    )

    duration = (
        downloaded.get("duration")
        if isinstance(
            downloaded.get("duration"),
            (int, float),
        )
        else metadata.get("duration")
    )

    return InstagramMedia(
        path=video_path,
        audio_path=audio_path,
        shortcode=_safe_shortcode(downloaded),
        title=title,
        description=description,
        channel=channel,
        duration_seconds=(
            int(duration)
            if isinstance(duration, (int, float))
            else None
        ),
        webpage_url=str(
            downloaded.get("webpage_url")
            or metadata.get("webpage_url")
            or normalized_url
        ),
    )
