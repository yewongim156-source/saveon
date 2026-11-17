from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))

from services.llm_postprocessor import postprocess_with_llm
from services.fact_verifier import verify_structured_claims
from services.verified_summary import apply_verified_summary


def main() -> None:
    output = ROOT / ".runtime" / "grounding-replay"
    output.mkdir(parents=True, exist_ok=True)
    for name in ("user-001", "user-005"):
        original = json.loads((ROOT / ".runtime" / "user-pilot-evidence" / name / "evidence.json").read_text(encoding="utf-8"))
        segments = [{"id": f"stt-{i:03d}", "modality": "STT", **segment} for i, segment in enumerate(original["transcript"]["segments"], 1)]
        ocr = []
        seen = set()
        for frame in original["frames"]:
            for entry in frame["ocr"]:
                text = entry["text"]
                if text.casefold() not in seen:
                    seen.add(text.casefold())
                    ocr.append({"id": f"ocr-{len(ocr)+1:03d}", "modality": "OCR", "text": text, "timeMs": frame["timeMs"]})
        evidence = segments + ocr
        try:
            result = postprocess_with_llm(transcript=" ".join(item["text"] for item in segments), ocr_lines=[item["text"] for item in ocr], vision_labels=[], evidence_units=evidence, source_title=original["source"]["title"], source_channel=original["source"]["creator"])
            result["structured"]["videoEvidence"] = evidence
            result["structured"] = verify_structured_claims(result["structured"])
            result = apply_verified_summary(result)
            (output / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{name}: targets={len(result['structured']['targets'])}, verification={result['structured']['verificationStatus']}", flush=True)
        except Exception as exc:
            print(f"{name}: failed: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
