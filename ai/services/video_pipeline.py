from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
import re
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


from services.llm_postprocessor import (
    GEMINI_MODEL,
    postprocess_with_llm,
)
from services.fact_verifier import verify_structured_claims
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
    "뷰티": ["화장", "메이크업", "립", "아이섀도", "beauty", "makeup"],
    "쇼핑": ["쇼핑", "구매", "가격", "제품", "shopping", "product"],
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
    "with", "this", "that", "from", "have", "your", "video",
}


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

    for frame_number in positions:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)

    capture.release()
    print(f"[VIDEO] sampled={len(frames)} total_frames={total_frames} fps={fps:.2f}")
    return frames


def sample_ocr_frames(video_path: Path, interval_seconds: float = 2.0, max_frames: int = 60) -> list[tuple[int, np.ndarray]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("영상 파일을 열 수 없습니다.")
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    if total <= 0 or fps <= 0:
        capture.release()
        return []
    stride = max(1, round(interval_seconds * fps), int(np.ceil(total / max_frames)))
    sampled = []
    for position in range(0, total, stride):
        capture.set(cv2.CAP_PROP_POS_FRAMES, position)
        ok, frame = capture.read()
        if ok and frame is not None:
            sampled.append((round(position * 1000 / fps), frame))
    capture.release()
    return sampled


def run_timed_ocr(frames: list[tuple[int, np.ndarray]]) -> list[dict]:
    if not frames:
        return []
    reader = _get_ocr()
    found = []
    seen = set()
    for time_ms, frame in frames:
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
    text = " ".join([source_text, transcript, *ocr_lines]).lower()
    categories: list[str] = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
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
    text = " ".join([source_text, transcript, *ocr_lines])
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
    entities = []
    for line in ocr_lines:
        clean = line.strip()
        if 2 <= len(clean) <= 30:
            entities.append(clean)
    return unique_preserve_order(entities)[:8]


def build_title(
    transcript: str,
    ocr_lines: list[str],
    categories: list[str],
    source_title: str = "",
) -> str:
    cleaned_source_title = " ".join(source_title.split()).strip()
    if cleaned_source_title:
        return cleaned_source_title[:80]

    if ocr_lines:
        title = ocr_lines[0][:40]
        if title:
            return title

    sentence = re.split(r"[.!?。]\s*", transcript, maxsplit=1)[0].strip()
    if sentence:
        return sentence[:40]

    if categories:
        return f"{categories[0]} 영상 분석 결과"

    return "영상 분석 결과"


def build_summary(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
    source_description: str = "",
    source_channel: str = "",
) -> str:
    pieces = []

    if transcript:
        pieces.append(f"음성 내용: {transcript[:260]}")

    if ocr_lines:
        pieces.append("화면 텍스트: " + ", ".join(ocr_lines[:6]))

    if vision_labels and not transcript and not ocr_lines:
        readable = [
            VISION_TO_CATEGORY.get(label, label)
            for label in vision_labels
        ]
        pieces.append("화면 유형: " + ", ".join(readable))

    cleaned_description = " ".join(source_description.split()).strip()
    # Descriptions can be promotional or changed after upload. Use one only
    # when no content-derived text is available.
    if cleaned_description and not transcript and not ocr_lines:
        pieces.append(f"영상 설명: {cleaned_description[:220]}")

    cleaned_channel = " ".join(source_channel.split()).strip()
    if cleaned_channel:
        pieces.append(f"출처 채널: {cleaned_channel[:80]}")

    if not pieces:
        return "영상에서 분석 가능한 음성 또는 화면 텍스트를 충분히 찾지 못했습니다."

    return " / ".join(pieces)[:900]


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
        # Silent or video-only sources can still produce useful OCR and visual
        # results, so lack of a decodable audio track is not fatal.
        print(f"[AUDIO] 음성 분석 실패 - 화면 분석만 진행: {exc}")
        transcript = ""
        transcript_segments = []

    with pipeline_step(
        "frame-sampling",
        kind="TOOL",
    ) as step:
        frames = sample_frames(video_path)
        step.set_output({"frameCount": len(frames)})

    with pipeline_step(
        "screen-text-ocr",
        kind="TOOL",
        model="easyocr-ko-en",
        input_summary={"frameCount": len(frames)},
    ) as step:
        timed_ocr = run_timed_ocr(sample_ocr_frames(
            video_path,
            interval_seconds=float(os.getenv("OCR_INTERVAL_SECONDS", "2")),
            max_frames=int(os.getenv("OCR_MAX_FRAMES", "60")),
        ))
        ocr_lines = [item["text"] for item in timed_ocr]
        step.set_output({"lineCount": len(ocr_lines)})

    with pipeline_step(
        "visual-classification",
        kind="TOOL",
        model=os.getenv(
            "CLIP_MODEL",
            "openai/clip-vit-base-patch32",
        ),
        input_summary={"frameCount": len(frames)},
    ) as step:
        vision_labels = run_vision(frames)
        step.set_output({"labels": vision_labels})

    # The title is a useful supporting hint. The description is intentionally
    # excluded from deterministic classification because it is not guaranteed
    # to describe the actual clip.
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
        ),
        "summary": build_summary(
            transcript,
            ocr_lines,
            vision_labels,
            source_description,
            source_channel,
        ),
        "categories": categories,
        "keywords": keywords,
        "entities": entities,
        "structured": {
            "primaryCategory": fallback_primary_category,
            "secondaryCategories": categories[:3],
            "tags": keywords[:8],
            "contentType": "OTHER",
            "entityDetails": [
                {
                    "name": entity,
                    "type": "OTHER",
                    "confidence": 0.0,
                }
                for entity in entities
            ],
            "claims": [],
            "factChecks": [],
        },
    }

    try:
        with pipeline_step(
            "content-structuring",
            kind="AGENT",
            model=GEMINI_MODEL,
            prompt_version="content-structuring-v1",
            input_summary={
                "transcriptCharacters": len(transcript),
                "ocrLineCount": len(ocr_lines),
                "visionLabels": vision_labels,
            },
        ) as step:
            result = postprocess_with_llm(
                transcript=transcript,
                ocr_lines=ocr_lines,
                evidence_units=transcript_segments + timed_ocr,
                # The current CLIP classifier is restricted to a small fixed
                # label set. Keep it as a last-resort signal rather than
                # contaminating otherwise useful STT/OCR evidence.
                vision_labels=(
                    vision_labels
                    if not transcript and not ocr_lines
                    else []
                ),
                source_title=source_title,
                source_description=source_description,
                source_channel=source_channel,
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
            })

        # 혹시 Gemini가 특정 필드를 비워 반환하면
        # 기존 멀티모달 분석 결과로 보완한다.
        for key in (
            "title",
            "summary",
            "categories",
            "keywords",
            "entities",
            "structured",
        ):
            if not result.get(key):
                result[key] = fallback_result[key]

        print("[VIDEO] Gemini 후처리 사용")

    except Exception as exc:
        print(
            "[LLM] Gemini 후처리 실패 "
            f"- fallback 사용: {exc}"
        )
        result = fallback_result
        result["summary"] = "AI 요약을 생성하지 못했습니다. 원본 영상을 확인하거나 다시 분석해 주세요."
        result["entities"] = []
        result["structured"]["entityDetails"] = []
        result["structured"]["analysisQuality"] = "FALLBACK"

    result["structured"]["ocrEvidence"] = timed_ocr
    result["structured"]["videoEvidence"] = transcript_segments + timed_ocr
    result["structured"]["promptVariant"] = prompt_variant

    result["structured"] = verify_structured_claims(
        result.get("structured", {})
    )
    result = apply_verified_summary(result)
    from services.external_reference import add_educational_reference
    result = add_educational_reference(result)

    print("[VIDEO] 분석 완료")
    print(f"[VIDEO] transcript={transcript[:120]}")
    print(f"[VIDEO] ocr={ocr_lines[:5]}")
    print(f"[VIDEO] vision={vision_labels}")
    print(f"[VIDEO] result={result}")

    return result
