"""Optional creator-authorized Reel preview from frames already sampled for OCR/CLIP.

No fetching, cookies, or metadata probing. The caller alone controls whether this
function is invoked after receiving a thumbnail-storage permission flag.
"""
from __future__ import annotations

import base64
import cv2
import numpy as np

MAX_JPEG_BYTES = 180_000


def frame_thumbnail_base64(frames: list[np.ndarray]) -> str | None:
    """Pick a nonblank, comparatively sharp frame; make a small JPEG."""
    if not frames:
        return None

    candidates: list[tuple[float, np.ndarray]] = []
    for frame in frames[:8]:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.size == 0:
            continue
        height, width = frame.shape[:2]
        if width < 16 or height < 16:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        luminance = float(gray.mean())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if luminance <= 15 or luminance >= 245 or sharpness < 2:
            continue
        # Avoid a black/white title screen; prefer readable video content.
        score = min(sharpness, 800.0) - abs(luminance - 125.0) * 0.7
        candidates.append((score, frame))
    if not candidates:
        return None

    frame = max(candidates, key=lambda item: item[0])[1]
    height, width = frame.shape[:2]
    scale = min(1.0, 384.0 / width, 640.0 / height)
    if scale < 1:
        frame = cv2.resize(
            frame, (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    for quality in (76, 65, 52):
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok and 100 < len(encoded) <= MAX_JPEG_BYTES:
            return base64.b64encode(encoded.tobytes()).decode("ascii")
    return None
