from __future__ import annotations

import json
import argparse
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".runtime" / "user-pilot-results"


def request(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--id", action="append", dest="ids")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = json.loads((ROOT / "evaluation" / "user_sources.json").read_text(encoding="utf-8"))["sources"]
    if args.ids:
        sources = [source for source in sources if source["id"] in args.ids]
    for index, source in enumerate(sources, 1):
        started = time.monotonic()
        result = {"source": source, "startedAt": datetime.now(timezone.utc).isoformat()}
        try:
            content = request("http://127.0.0.1:8080/api/v1/contents", {"sourceUrl": source["url"], "platform": "YOUTUBE"})
            result["contentId"] = content["id"]
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                content = request(f"http://127.0.0.1:8080/api/v1/contents/{content['id']}")
                if content.get("status") in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(3)
            result["content"] = content
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        result["elapsedSeconds"] = round(time.monotonic() - started, 2)
        (args.output / f"{source['id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{index}/{len(sources)}] {source['id']} {result.get('content', {}).get('status', result.get('error'))} {result['elapsedSeconds']}s", flush=True)


if __name__ == "__main__":
    main()
