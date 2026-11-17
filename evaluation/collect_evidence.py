from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = PROJECT_ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from services.video_pipeline import _get_ocr, _get_whisper  # noqa: E402
from services.youtube_source import download_youtube_video  # noqa: E402


def _sample_positions(video_path: Path, maximum: int) -> list[tuple[int, int]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    capture.release()
    if total_frames <= 0 or fps <= 0:
        return []

    positions = np.linspace(
        0,
        total_frames - 1,
        num=min(maximum, total_frames),
        dtype=int,
    )
    return [
        (int(position), int(round(position / fps * 1000)))
        for position in positions
    ]


def _collect_frames(
    video_path: Path,
    output_dir: Path,
    maximum: int,
) -> list[dict]:
    reader = _get_ocr()
    positions = _sample_positions(video_path, maximum)
    capture = cv2.VideoCapture(str(video_path))
    frames: list[dict] = []

    for index, (frame_number, time_ms) in enumerate(positions):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue

        image_name = f"frame-{index:02d}-{time_ms:06d}ms.jpg"
        image_path = output_dir / image_name
        encoded, buffer = cv2.imencode(".jpg", frame)
        if not encoded:
            raise RuntimeError(f"Cannot encode frame: {image_path}")
        buffer.tofile(str(image_path))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ocr_items = []
        for _, text, confidence in reader.readtext(
            rgb,
            detail=1,
            paragraph=False,
        ):
            cleaned = " ".join(str(text).split()).strip()
            if len(cleaned) >= 2:
                ocr_items.append({
                    "text": cleaned,
                    "confidence": round(float(confidence), 4),
                })

        frames.append({
            "frameIndex": index,
            "frameNumber": frame_number,
            "timeMs": time_ms,
            "image": image_name,
            "ocr": ocr_items,
        })

    capture.release()
    return frames


def _collect_transcript(audio_path: Path) -> list[dict]:
    model = _get_whisper()
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=3,
        vad_filter=True,
    )
    result = []
    for segment in segments:
        text = " ".join(segment.text.split()).strip()
        if text:
            result.append({
                "startMs": int(round(segment.start * 1000)),
                "endMs": int(round(segment.end * 1000)),
                "text": text,
            })
    return [{
        "detectedLanguage": info.language,
        "languageProbability": round(float(info.language_probability), 4),
        "segments": result,
    }]


def collect_one(source: dict, output_root: Path, frames: int) -> dict:
    item_dir = output_root / source["id"]
    item_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="saveon-eval-") as raw_temp:
        media = download_youtube_video(source["url"], Path(raw_temp))
        transcript = _collect_transcript(media.audio_path or media.path)
        sampled_frames = _collect_frames(media.path, item_dir, frames)

    evidence = {
        "id": source["id"],
        "source": {
            "platform": "YOUTUBE",
            "url": media.webpage_url,
            "videoId": media.video_id,
            "title": media.title,
            "creator": media.channel,
            "description": media.description,
            "durationSeconds": media.duration_seconds,
        },
        "transcript": transcript[0],
        "frames": sampled_frames,
    }
    (item_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect temporary STT/OCR evidence for pilot annotation."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path(__file__).with_name("pilot_sources.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".runtime" / "evaluation-evidence",
    )
    parser.add_argument("--id", action="append", dest="ids")
    parser.add_argument("--frames", type=int, default=10)
    args = parser.parse_args()

    payload = json.loads(args.sources.read_text(encoding="utf-8"))
    selected = [
        source
        for source in payload["sources"]
        if not args.ids or source["id"] in set(args.ids)
    ]
    if not selected:
        raise SystemExit("No matching pilot sources.")

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    failures = []
    for index, source in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] collecting {source['id']}")
        try:
            manifest.append(collect_one(source, args.output, args.frames))
        except Exception as exc:
            failure = {
                "id": source["id"],
                "url": source["url"],
                "error": str(exc),
            }
            failures.append(failure)
            print(f"[failed] {source['id']}: {exc}")

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Evidence written under: {args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
