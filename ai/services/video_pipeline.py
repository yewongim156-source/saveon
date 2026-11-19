from __future__ import annotations

from collections import Counter
from contextlib import closing
from pathlib import Path
import os
import re
from typing import Generator, Iterable

import cv2
import numpy as np
from PIL import Image

from services.reel_thumbnail import frame_thumbnail_base64
from services.llm_postprocessor import (
    GEMINI_MODEL,
    postprocess_with_llm,
)
from services.video_observations import extract_video_observations, review_excerpt_lines
from services.category_quality_guard import refine_analysis_categories
from services.fact_verifier import verify_structured_claims
# SAVEON_QUALITY_GUARD_V9
from services.verified_summary import apply_verified_summary
from services.telemetry import pipeline_step


_WHISPER_MODEL = None
_OCR_READER = None
_CLIP_MODEL = None
_CLIP_PROCESSOR = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_CACHE_ROOT = Path(
    os.getenv(
        "SAVEON_MODEL_CACHE_DIR",
        str(PROJECT_ROOT / ".runtime" / "model-cache"),
    )
).expanduser().resolve()


def _model_cache_dir(name: str | Path) -> Path:
    path = MODEL_CACHE_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path

VISION_LABELS = [
    "food", "cafe", "travel", "beauty", "shopping",
    "fashion", "technology", "study", "fitness", "daily life",
]

CATEGORY_KEYWORDS = {
    "맛집": ["맛집", "음식", "메뉴", "먹", "food", "restaurant"],
    "카페": ["카페", "커피", "디저트", "cafe", "coffee"],
    "여행": ["여행", "관광", "호텔", "숙소", "travel", "trip"],
    "뷰티": [
        "화장", "메이크업", "립", "아이섀도", "쿠션",
        "파운데이션", "블러셔", "뷰티", "코덕",
        "beauty", "makeup",
    ],
    "쇼핑": [
        "쇼핑", "구매", "가격", "제품", "추천템",
        "shopping", "product",
    ],
    "패션": ["패션", "코디", "옷", "신발", "fashion"],
    "공부": ["공부", "강의", "시험", "study", "lecture"],
    "기술": ["개발", "코딩", "앱", "AI", "기술", "technology", "coding"],
    "운동": ["운동", "헬스", "러닝", "fitness", "workout"],
}

VISION_TO_CATEGORY = {
    "food": "맛집",
    "cafe": "카페",
    "travel": "여행",
    "beauty": "뷰티",
    "shopping": "쇼핑",
    "fashion": "패션",
    "technology": "기술",
    "study": "공부",
    "fitness": "운동",
    "daily life": "생활",
}

LEGACY_CATEGORY_TO_PRIMARY = {
    "맛집": "음식/레시피",
    "카페": "음식/레시피",
    "여행": "장소/여행",
    "뷰티": "뷰티/패션",
    "쇼핑": "제품/쇼핑",
    "패션": "뷰티/패션",
    "공부": "학습/커리어",
    "기술": "생활정보",
    "운동": "건강/운동",
    "생활": "생활정보",
    "영상": "기타",
}

STOPWORDS = {
    "그리고", "하지만", "그냥", "이거", "저거", "영상", "콘텐츠",
    "진짜", "정말", "오늘", "여기", "저기", "하는", "있는", "없는",
    "with", "this", "that", "from", "have", "your", "video", "reel", "by",
}

GENERIC_SOURCE_TITLE_PATTERNS = [
    re.compile(r"^video\s+by\s+.+$", re.I),
    re.compile(r"^reel\s+by\s+.+$", re.I),
    re.compile(r"^instagram\s+video$", re.I),
    re.compile(r"^youtube\s+video$", re.I),
]


def _get_whisper():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        model_name = os.getenv("WHISPER_MODEL", "base")
        _WHISPER_MODEL = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(_model_cache_dir("whisper")),
        )
    return _WHISPER_MODEL


def _get_ocr():
    global _OCR_READER
    if _OCR_READER is None:
        import easyocr
        _OCR_READER = easyocr.Reader(
            ["ko", "en"],
            gpu=False,
            verbose=False,
            model_storage_directory=str(
                _model_cache_dir(Path("easyocr") / "model")
            ),
            user_network_directory=str(
                _model_cache_dir(Path("easyocr") / "user_network")
            ),
        )
    return _OCR_READER


def _get_clip():
    global _CLIP_MODEL, _CLIP_PROCESSOR
    if _CLIP_MODEL is None or _CLIP_PROCESSOR is None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            model_name = os.getenv(
                "CLIP_MODEL",
                "openai/clip-vit-base-patch32",
            )
            cache_dir = str(_model_cache_dir("huggingface"))
            _CLIP_PROCESSOR = CLIPProcessor.from_pretrained(
                model_name,
                cache_dir=cache_dir,
            )
            _CLIP_MODEL = CLIPModel.from_pretrained(
                model_name,
                cache_dir=cache_dir,
            )
            _CLIP_MODEL.eval()
        except Exception as exc:
            print(f"[VISION] CLIP 로딩 실패 - 건너뜀: {exc}")
            return None, None
    return _CLIP_MODEL, _CLIP_PROCESSOR


def transcribe_video(video_path: Path) -> str:
    return " ".join(item["text"] for item in transcribe_segments(video_path))


def transcribe_segments(video_path: Path) -> list[dict]:
    model = _get_whisper()
    segments, _ = model.transcribe(
        str(video_path),
        beam_size=3,
        vad_filter=True,
    )
    chunks = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            chunks.append({"id": f"stt-{len(chunks)+1:03d}", "text": text, "startMs": round(segment.start * 1000), "endMs": round(segment.end * 1000), "modality": "STT"})
    return chunks


def sample_frames(video_path: Path, max_frames: int = 6) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("영상 파일을 열 수 없습니다.")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames: list[np.ndarray] = []

    if total_frames <= 0:
        capture.release()
        return frames

    positions = np.linspace(
        0,
        max(total_frames - 1, 0),
        num=min(max_frames, total_frames),
        dtype=int,
    )

    for position in positions:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(position))
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)

    capture.release()
    print(
        f"[VIDEO] sampled={len(frames)} "
        f"total_frames={total_frames} fps={fps:.2f}"
    )
    return frames


def sample_ocr_frames(
    video_path: Path, interval_seconds: float = 0.75, max_frames: int = 120,
) -> Generator[tuple[int, np.ndarray], None, None]:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise RuntimeError("영상 파일을 열 수 없습니다.")
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        if total <= 0 or fps <= 0:
            return
        stride = max(1, round(interval_seconds * fps), int(np.ceil(total / max_frames)))
        for position in range(0, total, stride):
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            ok, frame = capture.read()
            if ok and frame is not None:
                yield round(position * 1000 / fps), frame
    finally:
        capture.release()


def run_timed_ocr(frames: Iterable[tuple[int, np.ndarray]]) -> list[dict]:
    reader = None
    found = []
    seen = set()
    for time_ms, frame in frames:
        if reader is None:
            reader = _get_ocr()
        lines = reader.readtext(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), detail=0, paragraph=False)
        for line in lines:
            text = " ".join(str(line).split()).strip()
            key = text.casefold()
            if len(text) >= 2 and key not in seen:
                seen.add(key)
                found.append({"id": f"ocr-{len(found)+1:03d}", "text": text, "timeMs": time_ms, "modality": "OCR"})
    return found[:150]


def run_ocr(frames: list[np.ndarray]) -> list[str]:
    if not frames:
        return []

    reader = _get_ocr()
    found: list[str] = []

    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lines = reader.readtext(
            rgb,
            detail=0,
            paragraph=False,
        )
        for line in lines:
            cleaned = " ".join(str(line).split()).strip()
            if len(cleaned) >= 2:
                found.append(cleaned)

    return unique_preserve_order(found)[:30]


def run_vision(frames: list[np.ndarray]) -> list[str]:
    if not frames:
        return []

    model, processor = _get_clip()
    if model is None or processor is None:
        return []

    import torch

    scores = Counter()

    for frame in frames[:6]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        inputs = processor(
            text=VISION_LABELS,
            images=image,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0]

        top_indices = probs.topk(
            k=min(2, len(VISION_LABELS))
        ).indices.tolist()

        for idx in top_indices:
            scores[VISION_LABELS[idx]] += 1

    return [label for label, _ in scores.most_common(3)]


def build_categories(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
    source_text: str = "",
) -> list[str]:
    # publisher metadata first so strong caption evidence wins before noisy OCR/vision
    ordered_text = " ".join(
        [source_text, source_text, transcript, *ocr_lines]
    ).lower()
    categories: list[str] = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(
            keyword.lower() in ordered_text
            for keyword in keywords
        ):
            categories.append(category)

    # CLIP uses a small fixed label set and can force an unrelated category.
    # Treat it as a last-resort signal only when text evidence is unavailable.
    if not transcript.strip() and not ocr_lines:
        for label in vision_labels:
            category = VISION_TO_CATEGORY.get(label)
            if category and category not in categories:
                categories.append(category)

    if not categories:
        categories.append("영상")

    return categories[:4]


def extract_keywords(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
    source_text: str = "",
) -> list[str]:
    # source metadata is duplicated intentionally to increase stable publisher signal
    text = " ".join(
        [source_text, source_text, transcript, *ocr_lines]
    )
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", text)
    normalized = [
        word
        for word in words
        if word.lower() not in STOPWORDS
    ]

    counts = Counter(normalized)
    keywords = [word for word, _ in counts.most_common(8)]

    if not transcript.strip() and not ocr_lines:
        for label in vision_labels:
            translated = VISION_TO_CATEGORY.get(label, label)
            if translated not in keywords:
                keywords.append(translated)

    return keywords[:10]


def extract_entities(ocr_lines: list[str]) -> list[str]:
    # OCR only로 엔티티를 만드는 fallback은 오탐 비용이 매우 높다.
    # Gemini 후처리에 실패한 경우에도 무의미한 OCR 조각을 사용자 데이터로
    # 저장하지 않는 편이 안전하다.
    return []


def _generic_source_title(value: str) -> bool:
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return True

    return any(
        pattern.match(cleaned)
        for pattern in GENERIC_SOURCE_TITLE_PATTERNS
    )


def _description_title(source_description: str) -> str:
    cleaned = " ".join(
        source_description.split()
    ).strip()
    if not cleaned:
        return ""

    before_tags = cleaned.split("#", 1)[0].strip()
    candidate = before_tags or cleaned
    return candidate[:80]


def build_title(
    transcript: str,
    ocr_lines: list[str],
    categories: list[str],
    source_title: str = "",
    source_description: str = "",
) -> str:
    cleaned_source_title = " ".join(source_title.split()).strip()

    if cleaned_source_title and not _generic_source_title(
        cleaned_source_title
    ):
        return cleaned_source_title[:80]

    from_description = _description_title(
        source_description
    )
    if from_description:
        return from_description

    if ocr_lines:
        title = ocr_lines[0][:40]
        if title:
            return title

    sentence = re.split(
        r"[.!?。]\s*",
        transcript,
        maxsplit=1,
    )[0].strip()

    if sentence:
        return sentence[:40]

    if categories:
        return f"{categories[0]} 영상"

    return "저장한 영상"


def build_summary(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
    source_description: str = "",
    source_channel: str = "",
) -> str:

    # SAVEON_MERGE_PRIMARY_EVIDENCE
    # 영상 내용이 있으면 외부 설명보다 우선한다.
    if transcript and transcript.strip():
        cleaned = " ".join(transcript.split())
        return ("영상에서 " + cleaned[:420])[:500]

    if ocr_lines:
        readable = [
            str(value).strip()
            for value in ocr_lines[:4]
            if str(value).strip()
        ]
        if readable:
            return (
                "영상 화면에서 "
                + ", ".join(readable)
                + " 관련 내용을 확인했어요."
            )[:500]

    cleaned_description = " ".join(
        source_description.split()
    ).strip()

    # fallback에서도 사용자-facing 문장으로 시작한다.
    if cleaned_description:
        return cleaned_description[:500]

    if transcript:
        cleaned_transcript = " ".join(
            transcript.split()
        ).strip()
        if cleaned_transcript:
            return (
                "영상에서 "
                + cleaned_transcript[:420]
            )[:500]

    if ocr_lines:
        meaningful = ", ".join(
            ocr_lines[:4]
        )
        if meaningful:
            return (
                "영상 화면에서 "
                + meaningful
                + " 관련 내용을 확인했어요."
            )[:500]

    if vision_labels and not transcript and not ocr_lines:
        readable = [
            VISION_TO_CATEGORY.get(label, label)
            for label in vision_labels
        ]
        return (
            ", ".join(readable)
            + " 관련 영상으로 분류했어요."
        )[:500]

    return "영상에서 분석 가능한 내용을 충분히 찾지 못했어요."


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def analyze_video_file(
    video_path: Path,
    *,
    audio_path: Path | None = None,
    source_title: str = "",
    source_description: str = "",
    source_channel: str = "",
    thumbnail_requested: bool = False,
    prompt_variant: str = "baseline",
) -> dict:
    print(f"[VIDEO] 분석 시작: {video_path.name}")

    transcript_source = audio_path or video_path
    try:
        with pipeline_step(
            "speech-to-text",
            kind="TOOL",
            model=os.getenv("WHISPER_MODEL", "base"),
            input_summary={"hasSeparateAudio": audio_path is not None},
        ) as step:
            transcript_segments = transcribe_segments(transcript_source)
            transcript = " ".join(item["text"] for item in transcript_segments)
            step.set_output({
                "characters": len(transcript),
                "hasTranscript": bool(transcript),
            })
    except Exception as exc:
        print(f"[AUDIO] 음성 분석 실패 - 화면 분석만 진행: {exc}")
        transcript = ""
        transcript_segments = []

    ocr_interval = float(os.getenv("OCR_INTERVAL_SECONDS", "0.75"))
    ocr_max_frames = int(os.getenv("OCR_MAX_FRAMES", "120"))
    with pipeline_step(
        "screen-text-ocr",
        kind="TOOL",
        model="easyocr-ko-en",
        input_summary={"intervalSeconds": ocr_interval, "maxFrames": ocr_max_frames},
    ) as step:
        with closing(sample_ocr_frames(video_path, ocr_interval, ocr_max_frames)) as frames:
            timed_ocr = run_timed_ocr(frames)
        ocr_lines = [item["text"] for item in timed_ocr]
        step.set_output({"lineCount": len(ocr_lines)})

    needs_vision = not transcript.strip() and not ocr_lines
    preview_frames = []
    if needs_vision or thumbnail_requested:
        with pipeline_step("frame-sampling", kind="TOOL") as step:
            preview_frames = sample_frames(video_path)
            step.set_output({"frameCount": len(preview_frames)})

    thumbnail_base64 = None
    if thumbnail_requested:
        try:
            thumbnail_base64 = frame_thumbnail_base64(preview_frames)
        except Exception as exc:
            print(f"[THUMBNAIL] Optional preview skipped: {type(exc).__name__}")

    with pipeline_step(
        "visual-classification",
        kind="TOOL",
        model=os.getenv(
            "CLIP_MODEL",
            "openai/clip-vit-base-patch32",
        ),
        input_summary={"frameCount": len(preview_frames) if needs_vision else 0},
    ) as step:
        vision_labels = run_vision(preview_frames) if needs_vision else []
        step.set_output({"labels": vision_labels, "skipped": not needs_vision})

    # SAVEON_VIDEO_OBSERVATIONS_V8: retain provenance from original inputs.
    observations = extract_video_observations(
        transcript=transcript,
        ocr_lines=ocr_lines,
        source_title=source_title,
        source_description=source_description,
    )

    # A source title can help classification; a promotional description
    # must not override evidence from the actual video.
    source_text = source_title.strip()

    categories = build_categories(
        transcript,
        ocr_lines,
        vision_labels,
        source_text,
    )
    keywords = extract_keywords(
        transcript,
        ocr_lines,
        vision_labels,
        source_text,
    )
    entities = extract_entities(ocr_lines)

    fallback_primary_category = "기타"
    for category in categories:
        mapped = LEGACY_CATEGORY_TO_PRIMARY.get(category)
        if mapped:
            fallback_primary_category = mapped
            break

    fallback_result = {
        "title": build_title(
            transcript,
            ocr_lines,
            categories,
            source_title,
            source_description,
        ),
        "summary": build_summary(
            transcript,
            ocr_lines,
            vision_labels,
            source_description,
            source_channel,
        ),
        "categories": [
            fallback_primary_category
        ] if fallback_primary_category != "기타" else ["기타"],
        "keywords": keywords,
        "entities": entities,
        "structured": {
            "primaryCategory": fallback_primary_category,
            "secondaryCategories": categories[:3],
            "tags": keywords[:8],
            "contentType": "OTHER",
            "entityDetails": [],
            "claims": [],
            "factChecks": [],
        },
    }

    try:
        with pipeline_step(
            "content-structuring",
            kind="AGENT",
            model=GEMINI_MODEL,
            prompt_version="content-structuring-v2-quality",
            input_summary={
                "transcriptCharacters": len(transcript),
                "ocrLineCount": len(ocr_lines),
                "visionLabels": vision_labels,
                "hasSourceDescription": bool(source_description),
            },
        ) as step:
            result = postprocess_with_llm(
                transcript=transcript,
                ocr_lines=ocr_lines,
                evidence_units=transcript_segments + timed_ocr,
                # CLIP labels are coarse; only use them without STT/OCR.
                vision_labels=(
                    vision_labels
                    if not transcript and not ocr_lines
                    else []
                ),
                source_title=source_title,
                source_description=source_description,
                source_channel=source_channel,
                review_excerpts=review_excerpt_lines(observations),
                prompt_variant=prompt_variant,
            )
            step.set_output({
                "primaryCategory": (
                    result.get("structured", {})
                    .get("primaryCategory")
                ),
                "claimCount": len(
                    result.get("structured", {}).get("claims", [])
                ),
                "entityCount": len(
                    result.get("structured", {}).get(
                        "entityDetails",
                        [],
                    )
                ),
            })

        for key in (
            "title",
            "summary",
            "categories",
            "keywords",
            "structured",
        ):
            if not result.get(key):
                result[key] = fallback_result[key]

        # entities는 빈 배열이 정상일 수 있다.
        if "entities" not in result:
            result["entities"] = []

        print("[VIDEO] Gemini 후처리 사용")

    except Exception as exc:
        print(
            "[LLM] Gemini 후처리 실패 "
            f"- 품질 보호 fallback 사용: {exc}"
        )
        result = fallback_result
        result["summary"] = "AI 요약을 생성하지 못했습니다. 원본 영상을 확인하거나 다시 분석해 주세요."
        result["entities"] = []
        result["structured"]["entityDetails"] = []
        result["structured"]["analysisQuality"] = "FALLBACK"

    result["structured"]["ocrEvidence"] = timed_ocr
    result["structured"]["videoEvidence"] = transcript_segments + timed_ocr
    result["structured"]["promptVariant"] = prompt_variant

    # Immutable source excerpts; not ground-truth product specifications.
    if isinstance(result.get("structured"), dict):
        result["structured"]["videoObservations"] = observations

    result["structured"] = verify_structured_claims(
        result.get("structured", {})
    )
    result = apply_verified_summary(result)
    from services.external_reference import add_educational_reference
    result = add_educational_reference(result)
    # Remove redundant broad labels only, after Gemini/fallback/verification.
    result = refine_analysis_categories(result, source_title=source_title)

    if thumbnail_requested and thumbnail_base64 is not None:
        result["thumbnailBase64"] = thumbnail_base64

    print("[VIDEO] 분석 완료")
    print(f"[VIDEO] transcript={transcript[:120]}")
    print(f"[VIDEO] ocr={ocr_lines[:5]}")
    print(f"[VIDEO] vision={vision_labels}")
    print(f"[VIDEO] result keys={list(result)} thumbnail={bool(thumbnail_base64)}")

    return result
# SAVEON_INSTAGRAM_THUMBNAIL_V1
