"""Read overlay text on a few key frames with Gemini vision.

EasyOCR is fast but misreads small, stylized overlay text such as product cards
("히어썸웨어 이든 스트라이프 티셔츠 ₩27,000" came out as "기돈 스트라이프 ...") and recipe
amounts ("물엿 0.5스푼" -> "물엿 0 3스푼"). Narrowing the sampling interval does not
help because the frame is already captured; the engine misreads the same pixels.

Only frames that look like cards or amounts (a price or a quantity was detected) are
sent, at most MAX_FRAMES per video. The lines the model reads replace the noisy
EasyOCR lines of that same frame. Any failure keeps the EasyOCR result unchanged.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import cv2

from google.genai import types

from services.llm_postprocessor import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    _generate_with_retry,
    create_gemini_client,
)

# A list video can show 6+ product cards; a lower limit left later cards garbled.
MAX_FRAMES = int(os.getenv("OCR_VISION_MAX_FRAMES", "8"))
MIN_GAP_MS = 1500
MAX_LINES_PER_FRAME = 12

# A price (27,000원, ₩27,000) or a cooking/exercise quantity (0.5스푼, 200ml, 40회).
CARD_PATTERN = re.compile(
    r"\d{1,3}(?:,\d{3})+|[₩￦]\s*\d|\d+\s*원|\d+(?:\.\d+)?\s*(?:스푼|큰술|작은술|ml|mL|컵)"
)

PROMPT = (
    "This is one frame of a short video. Transcribe only the overlay text that is part of the "
    "video graphics: product cards (brand, product name, price), recipe or workout amounts, "
    "numbered headings and titles. Do not include the video player interface or automatic "
    "captions. Copy the text exactly in reading order, keeping Korean spelling, English brand "
    "names and symbols such as ₩. If a character is unclear, give your best reading. "
    "Return at most 12 short lines."
)


def enabled() -> bool:
    return (
        os.getenv("OCR_VISION_REFINE", "true").strip().lower() in {"1", "true", "yes", "on"}
        and bool(GEMINI_API_KEY)
        and MAX_FRAMES > 0
    )


def select_overlay_times(timed_ocr: list[dict], max_frames: int | None = None,
                         min_gap_ms: int = MIN_GAP_MS) -> list[int]:
    """Frame times whose OCR lines contain the most prices/quantities, spread apart."""
    limit = MAX_FRAMES if max_frames is None else max_frames
    scores: dict[int, int] = {}
    for unit in timed_ocr:
        if CARD_PATTERN.search(str(unit.get("text", ""))):
            time_ms = int(unit.get("timeMs", 0))
            scores[time_ms] = scores.get(time_ms, 0) + 1
    chosen: list[int] = []
    for time_ms, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        if all(abs(time_ms - other) >= min_gap_ms for other in chosen):
            chosen.append(time_ms)
        if len(chosen) >= limit:
            break
    return sorted(chosen)


def grab_frame(video_path: Path, time_ms: int):
    capture = cv2.VideoCapture(str(video_path))
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, time_ms)
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def read_overlay_text(frame) -> list[str]:
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        return []
    part = types.Part.from_bytes(data=buffer.tobytes(), mime_type="image/jpeg")
    with create_gemini_client() as client:
        response = _generate_with_retry(
            client,
            model=GEMINI_MODEL,
            contents=[PROMPT, part],
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=700,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
                    "required": ["lines"],
                },
            ),
        )
    import json
    lines = json.loads(response.text or "{}").get("lines", [])
    cleaned = []
    for line in lines if isinstance(lines, list) else []:
        text = " ".join(str(line).split()).strip()
        if 2 <= len(text) <= 80 and text not in cleaned:
            cleaned.append(text)
    return cleaned[:MAX_LINES_PER_FRAME]


def refine_overlay_ocr(video_path: Path, timed_ocr: list[dict]) -> tuple[list[dict], dict]:
    stats = {"candidateFrames": 0, "refinedFrames": 0, "failedFrames": 0}
    if not enabled() or not timed_ocr:
        return timed_ocr, stats

    times = select_overlay_times(timed_ocr)
    stats["candidateFrames"] = len(times)
    units = list(timed_ocr)
    for time_ms in times:
        try:
            frame = grab_frame(video_path, time_ms)
            lines = read_overlay_text(frame) if frame is not None else []
        except Exception as exc:  # keep the EasyOCR lines if vision is unavailable
            print(f"[OVERLAY VISION] {time_ms}ms 건너뜀: {type(exc).__name__}")
            stats["failedFrames"] += 1
            continue
        if not lines:
            continue
        units = [unit for unit in units if unit.get("timeMs") != time_ms]
        units.extend(
            {"id": "", "text": line, "timeMs": time_ms, "modality": "OCR", "source": "gemini-vision"}
            for line in lines
        )
        stats["refinedFrames"] += 1

    units.sort(key=lambda unit: (unit.get("timeMs", 0), unit.get("source") == "gemini-vision"))
    for index, unit in enumerate(units, 1):
        unit["id"] = f"ocr-{index:03d}"
    return units[:150], stats
