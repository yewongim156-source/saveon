from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.1-flash-lite",
)

MAX_TRANSCRIPT_CHARS = 3500
MAX_OCR_LINES = 20
MAX_OCR_LINE_LENGTH = 80
MAX_VISION_LABELS = 5

ALLOWED_CATEGORIES = [
    "여행",
    "맛집",
    "카페",
    "쇼핑",
    "패션",
    "뷰티",
    "IT/전자기기",
    "음식/레시피",
    "생활정보",
    "공부",
    "운동",
    "엔터테인먼트",
    "기타",
]

UI_NOISE = {
    "esc",
    "caps",
    "caps lock",
    "shift",
    "ctrl",
    "alt",
    "enter",
    "tab",
    "space",
    "home",
    "end",
    "delete",
    "backspace",
    "command",
    "option",
}


def _clean_transcript(text: str) -> str:
    if not text:
        return ""

    cleaned = " ".join(text.split())

    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        cleaned = cleaned[:MAX_TRANSCRIPT_CHARS]

    return cleaned


def _looks_like_noise(text: str) -> bool:
    value = text.strip()

    if not value:
        return True

    lowered = value.lower()

    if lowered in UI_NOISE:
        return True

    if len(value) < 2:
        return True

    if len(value) > MAX_OCR_LINE_LENGTH:
        return True

    # 기호만 있는 OCR 제거
    if not re.search(r"[가-힣A-Za-z0-9]", value):
        return True

    # 영문/숫자/한글이 거의 없고 특수문자가 대부분인 경우 제거
    useful_chars = re.findall(
        r"[가-힣A-Za-z0-9]",
        value,
    )

    if len(useful_chars) < 2:
        return True

    return False


def _clean_ocr_lines(
    ocr_lines: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for line in ocr_lines:
        cleaned = " ".join(
            str(line).split()
        ).strip()

        if _looks_like_noise(cleaned):
            continue

        normalized = cleaned.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(cleaned)

        if len(result) >= MAX_OCR_LINES:
            break

    return result


def _clean_vision_labels(
    labels: list[str],
) -> list[str]:
    result: list[str] = []

    for label in labels:
        label = str(label).strip()

        if not label:
            continue

        if label not in result:
            result.append(label)

        if len(result) >= MAX_VISION_LABELS:
            break

    return result


def _normalize_string_list(
    value,
    max_items: int,
) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue

        cleaned = item.strip()

        if not cleaned:
            continue

        normalized = cleaned.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(cleaned)

        if len(result) >= max_items:
            break

    return result


def _normalize_result(
    result: dict,
) -> dict:
    title = str(
        result.get("title", "")
    ).strip()

    summary = str(
        result.get("summary", "")
    ).strip()

    categories = _normalize_string_list(
        result.get("categories", []),
        max_items=3,
    )

    categories = [
        category
        for category in categories
        if category in ALLOWED_CATEGORIES
    ]

    if not categories:
        categories = ["기타"]

    keywords = _normalize_string_list(
        result.get("keywords", []),
        max_items=10,
    )

    entities = _normalize_string_list(
        result.get("entities", []),
        max_items=8,
    )

    if not title:
        title = "영상 콘텐츠"

    if not summary:
        summary = "영상의 핵심 내용을 분석했습니다."

    return {
        "title": title[:60],
        "summary": summary[:500],
        "categories": categories,
        "keywords": keywords,
        "entities": entities,
    }


def postprocess_with_llm(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되어 있지 않습니다."
        )

    clean_transcript = _clean_transcript(
        transcript
    )

    clean_ocr = _clean_ocr_lines(
        ocr_lines
    )

    clean_vision = _clean_vision_labels(
        vision_labels
    )

    input_data = {
        "transcript": clean_transcript,
        "ocr": clean_ocr,
        "vision_labels": clean_vision,
    }

    prompt = f"""
You are the metadata analysis engine for an app called save:on.

save:on stores short-form social media content and helps users
find it later.

The following information was automatically extracted from a video.
The STT and OCR data may contain recognition errors.

Your task is to infer the main subject of the video and create
clean Korean metadata.

IMPORTANT RULES:

1. Correct obvious STT recognition errors only when the intended
   meaning is reasonably clear.

2. Ignore meaningless OCR fragments and UI text.

3. Do not invent brands, products, places, people, prices,
   specifications, or other facts that are not supported by
   the provided data.

4. The title must describe the actual main topic naturally in Korean.

5. The summary should contain 1-3 concise Korean sentences.

6. categories must contain 1-3 items and must be selected ONLY
   from this list:

{ALLOWED_CATEGORIES}

7. keywords should contain 5-10 useful terms that would help
   the user search for this content later.

8. entities should contain only meaningful named or identifiable
   things such as:
   - brand
   - product
   - place
   - restaurant
   - person
   - service

9. Do not put generic UI text such as Esc, Shift, Caps Lock,
   buttons, timestamps, or random OCR fragments into entities.

10. If an entity cannot be confidently identified, omit it.

11. Return JSON only.

INPUT DATA:

{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=700,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "summary": {
                        "type": "string",
                    },
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                },
                "required": [
                    "title",
                    "summary",
                    "categories",
                    "keywords",
                    "entities",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError(
            "Gemini 응답이 비어 있습니다."
        )

    try:
        parsed = json.loads(
            response.text
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini JSON 파싱 실패: {response.text}"
        ) from exc

    result = _normalize_result(
        parsed
    )

    print("[LLM] Gemini 후처리 완료")
    print(
        f"[LLM] input transcript chars="
        f"{len(clean_transcript)}"
    )
    print(
        f"[LLM] input ocr lines="
        f"{len(clean_ocr)}"
    )
    print(
        f"[LLM] result={result}"
    )

    return result