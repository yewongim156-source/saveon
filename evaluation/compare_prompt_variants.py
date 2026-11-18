"""Replay the same saved evidence with both prompt variants, without new media downloads."""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))
from services.llm_postprocessor import postprocess_with_llm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8105")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with urllib.request.urlopen(f"{args.api}/admin/evaluations/{args.item}", timeout=10) as response:
        data = json.load(response)
    run = next(item for item in data["runs"] if item["id"] == args.run)
    evidence = run["stt"] + run["ocr"]
    if not evidence:
        raise SystemExit("이 실행에는 저장된 STT/OCR 근거가 없습니다.")
    args.output.mkdir(parents=True, exist_ok=True)
    for variant in ("baseline", "few_shot_v1"):
        out = args.output / f"{variant}.json"
        if out.exists():
            raise SystemExit(f"기존 결과를 덮어쓰지 않습니다: {out}")
        try:
            with (args.output / f"{variant}.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                result = postprocess_with_llm(transcript=" ".join(x.get("text", "") for x in run["stt"]),
                    ocr_lines=[x.get("text", "") for x in run["ocr"]], vision_labels=[],
                    evidence_units=evidence, source_title=data["item"]["source"].get("title", ""), prompt_variant=variant)
            result["structured"]["videoEvidence"] = evidence
            result["structured"]["promptVariant"] = variant
            payload = {"evaluationConfig": {"promptVariant": variant}, "inputRunId": args.run, "inputItemId": args.item, "result": result}
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{variant}: 성공, 대상 {len(result['structured'].get('targets', []))}개")
        except Exception as exc:
            print(f"{variant}: 실패 ({type(exc).__name__})")


if __name__ == "__main__":
    main()
