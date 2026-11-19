from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import EvaluationAIDraft, EvaluationItem, EvaluationReview, EvaluationRun, PromptCandidate

ROOT = Path(__file__).resolve().parents[1]
router = APIRouter(prefix="/admin/evaluations", tags=["evaluations"])
RUNS = {
    "baseline": ("user-pilot-results", "기존 분석"),
    "after-v2": ("user-pilot-after-v2", "개선 후 분석"),
    "grounding-replay": ("grounding-replay", "기존 추출 데이터로 Gemini 재실행"),
}
REPLAY_RUNS = {"replay-baseline": "baseline.json", "replay-fewshot": "few_shot_v1.json"}
SPRING_API = os.getenv("SAVEON_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
AI_API = os.getenv("SAVEON_AI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def platform_for_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port:
            raise ValueError()
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"} and parsed.path not in {"", "/"}:
            return "YOUTUBE"
        if host in {"instagram.com", "www.instagram.com", "m.instagram.com"} and parsed.path.startswith("/reel/") and len(parsed.path.strip("/").split("/")) >= 2:
            return "INSTAGRAM"
    except ValueError:
        pass
    raise HTTPException(422, "YouTube 영상 또는 Instagram 릴스의 올바른 링크를 입력해 주세요.")


def seed(db: Session) -> None:
    """Import missing items only; never overwrite developer edits."""
    files = [("pilot", ROOT / "evaluation/pilot_v1.json"),
             ("user-pilot", ROOT / "evaluation/user_sources.json")]
    for dataset, path in files:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", data.get("sources", [])):
            item_id = item.get("id")
            if not item_id or db.get(EvaluationItem, item_id):
                continue
            if dataset == "user-pilot":
                item = {"id": item_id, "source": {"url": item["url"], "platform": "YOUTUBE", "title": item.get("category", "")},
                        "gold": {}, "annotation": {"status": "DRAFT", "notes": []}}
            db.add(EvaluationItem(id=item_id, dataset=dataset, payload_json=json.dumps(item, ensure_ascii=False), revision=1))
        db.flush()
    db.commit()


def as_response(item: EvaluationItem) -> dict:
    return {"dataset": item.dataset, "revision": item.revision, "item": json.loads(item.payload_json)}


def find_item(db: Session, item_id: str) -> EvaluationItem:
    item = db.get(EvaluationItem, item_id)
    if not item:
        raise HTTPException(404, "평가 영상을 찾을 수 없습니다.")
    return item


@router.get("")
def list_items(db: Session = Depends(get_db)):
    seed(db)
    return [as_response(item) for item in db.scalars(select(EvaluationItem).order_by(EvaluationItem.id)).all()]


class ItemUpdate(BaseModel):
    revision: int = Field(ge=1)
    gold: dict
    annotation: dict


class ItemCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=200)


class RunConfig(BaseModel):
    promptVariant: Literal["baseline", "few_shot_v1", "structured_v2"] = "baseline"


@router.post("", status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    url = payload.url.strip()
    platform = platform_for_url(url)
    item_id = "eval-" + uuid.uuid4().hex[:16]
    item = {"id": item_id, "source": {"url": url, "platform": platform, "title": payload.title.strip()},
            "gold": {}, "annotation": {"status": "DRAFT", "notes": []}}
    record = EvaluationItem(id=item_id, dataset="manual", payload_json=json.dumps(item, ensure_ascii=False), revision=1)
    db.add(record)
    db.commit()
    return as_response(record)


@router.put("/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    data = json.loads(item.payload_json)
    data["gold"] = payload.gold
    data["annotation"] = payload.annotation
    changed = db.execute(update(EvaluationItem).where(EvaluationItem.id == item_id, EvaluationItem.revision == payload.revision)
        .values(payload_json=json.dumps(data, ensure_ascii=False), revision=EvaluationItem.revision + 1))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "다른 곳에서 수정되었습니다. 다시 불러온 뒤 저장하세요.")
    db.commit()
    db.expire_all()
    return as_response(find_item(db, item_id))


def format_run(data: dict, key: str, label: str) -> dict:
    content = data.get("content", data)
    structured = content.get("structuredAnalysis", content.get("structured", {})) or {}
    if isinstance(structured, str):
        try:
            structured = json.loads(structured)
        except json.JSONDecodeError:
            structured = {}
    if not isinstance(structured, dict):
        structured = {}
    evidence = structured.get("videoEvidence", []) or []
    ocr = [x for x in evidence if isinstance(x, dict) and x.get("modality") == "OCR"] or structured.get("ocrEvidence", [])
    stt = [x for x in evidence if isinstance(x, dict) and x.get("modality") == "STT"]
    return {"id": key, "label": label, "status": content.get("status", "REPLAY"),
            "startedAt": data.get("startedAt"), "elapsedSeconds": data.get("elapsedSeconds"),
            "stt": stt, "ocr": ocr, "gemini": {"title": content.get("title"), "summary": content.get("summary"), "structured": structured},
            "raw": data}


def load_run(item_id: str, key: str) -> dict | None:
    # Paths are derived from fixed run names and validated evaluation IDs.
    if not item_id.startswith("user-") or not item_id[5:].isdigit():
        return None
    directory, label = RUNS[key]
    path = ROOT / ".runtime" / directory / f"{item_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return format_run(data, key, label)


def load_prompt_replay(item_id: str, key: str) -> dict | None:
    path = ROOT / ".runtime" / "prompt-comparison-user001-20261117" / REPLAY_RUNS[key]
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("inputItemId") != item_id:
        return None
    variant = data.get("evaluationConfig", {}).get("promptVariant", "")
    wrapped = {"content": data.get("result", {}), "inputRunId": data.get("inputRunId"), "evaluationConfig": data.get("evaluationConfig")}
    return format_run(wrapped, key, f"동일 근거 재실행 · {variant}")


def run_response(run: EvaluationRun) -> dict:
    content = json.loads(run.snapshot_json) if run.snapshot_json else {}
    variant = content.get("evaluationConfig", {}).get("promptVariant", "baseline")
    started = run.started_at.isoformat() if run.started_at else None
    data = {"content": content, "startedAt": started, "contentId": run.content_id, "error": run.error}
    result = format_run(data, run.id, f"평가 실행 ({variant}) · {started or ''}")
    result["status"] = run.status
    result["error"] = run.error
    return result


def execute_evaluation_run(run_id: str, url: str, prompt_variant: str, revision_input: dict | None = None) -> None:
    """Run directly against AI so evaluation never creates a library item."""
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        if not run:
            return
        run.status = "ANALYZING"
        db.commit()
        with httpx.Client(timeout=600, trust_env=False) as client:
            if revision_input is None:
                response = client.post(f"{AI_API}/analyze", json={"sourceUrl": url, "promptVariant": prompt_variant})
            else:
                response = client.post(f"{AI_API}/internal/revise-summary", json=revision_input, headers={
                    "X-Evaluation-Token": os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip(),
                })
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("structured"), dict):
            raise ValueError("invalid AI analysis response")
        content = {"status": "COMPLETED", "title": result.get("title"), "summary": result.get("summary"),
                   "structuredAnalysis": result["structured"], "categories": result.get("categories", []),
                   "keywords": result.get("keywords", []), "entities": result.get("entities", []),
                   "evaluationConfig": json.loads(run.snapshot_json or "{}").get(
                       "evaluationConfig", {"promptVariant": prompt_variant})}
        run.snapshot_json = json.dumps(content, ensure_ascii=False)
        run.status = "COMPLETED"
    except Exception:
        db.rollback()
        run = db.get(EvaluationRun, run_id)
        if not run:
            return
        run.status = "FAILED"
        run.error = "AI 분석에 실패했습니다. AI 서버 상태와 로그를 확인해 주세요."
    finally:
        if run:
            run.active_item = None
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        db.close()


@router.post("/{item_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(item_id: str, background_tasks: BackgroundTasks, payload: RunConfig | None = None, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    data = json.loads(item.payload_json)
    if data.get("evaluationStatus") == "EXCLUDED":
        raise HTTPException(400, "평가에서 제외된 영상입니다.")
    source = data.get("source", {})
    url = str(source.get("url", ""))
    platform_for_url(url)
    variant = payload.promptVariant if payload else "baseline"
    run = EvaluationRun(id=uuid.uuid4().hex, item_id=item_id, active_item=item_id, status="PENDING",
                        snapshot_json=json.dumps({"evaluationConfig": {"promptVariant": variant}}))
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이 영상의 분석이 이미 진행 중입니다.")
    background_tasks.add_task(execute_evaluation_run, run.id, url, variant)
    return run_response(run)


@router.post("/{item_id}/runs/{run_id}/refresh")
def refresh_run(item_id: str, run_id: str, db: Session = Depends(get_db)):
    run = db.get(EvaluationRun, run_id)
    if not run or run.item_id != item_id:
        raise HTTPException(404, "분석 실행을 찾을 수 없습니다.")
    if run.status in {"COMPLETED", "FAILED", "SUBMISSION_UNKNOWN"}:
        return run_response(run)
    # New evaluation-only jobs are persisted by the worker; no app record exists.
    if not run.content_id:
        return run_response(run)
    if not run.content_id.isdigit():
        raise HTTPException(409, "요청 전달 상태가 불명확합니다. 앱 서버를 확인해 주세요.")
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(f"{SPRING_API}/api/v1/contents/{run.content_id}")
            response.raise_for_status()
            content = response.json()
        run.status = str(content.get("status", run.status))
        run.snapshot_json = json.dumps(content, ensure_ascii=False)
        if run.status in {"COMPLETED", "FAILED"}:
            run.active_item = None
            run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(503, "앱 서버의 분석 상태를 확인할 수 없습니다. 잠시 후 다시 확인해 주세요.")
    return run_response(run)


@router.get("/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    result = as_response(item)
    live_runs = db.scalars(select(EvaluationRun).where(EvaluationRun.item_id == item_id).order_by(EvaluationRun.started_at.desc())).all()
    result["runs"] = [run_response(run) for run in live_runs] + [run for key in REPLAY_RUNS if (run := load_prompt_replay(item_id, key)) is not None] + [run for key in RUNS if (run := load_run(item_id, key)) is not None]
    reviews = db.scalars(select(EvaluationReview).where(EvaluationReview.item_id == item_id)).all()
    result["reviews"] = {review.run_id: {"revision": review.revision, "goldRevision": review.gold_revision,
        "stale": review.gold_revision != item.revision, "data": json.loads(review.payload_json)} for review in reviews}
    drafts = db.scalars(select(EvaluationAIDraft).where(
        EvaluationAIDraft.item_id == item_id, EvaluationAIDraft.gold_revision == item.revision)).all()
    result["aiDrafts"] = {draft.run_id: json.loads(draft.payload_json) for draft in drafts}
    return result


def publication_request(method: str, suffix: str = "", **kwargs):
    token = os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "평가 반영 기능이 설정되지 않았습니다.")
    endpoint = f"{SPRING_API}/api/v1/internal/evaluation-publications{suffix}"
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.request(method, endpoint, headers={"X-Evaluation-Token": token}, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            raise HTTPException(409, "영상이 다르거나 보관함 항목이 변경되었습니다. 다시 조회해 주세요.") from exc
        raise HTTPException(503, "앱 서버에서 평가 반영 요청을 처리할 수 없습니다. 서버 버전과 설정을 확인해 주세요.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "앱 서버에 연결할 수 없습니다.") from exc


@router.get("/{item_id}/publication-targets")
def publication_targets(item_id: str, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    source_url = json.loads(item.payload_json)["source"]["url"]
    return publication_request("GET", params={"sourceUrl": source_url})


class PublicationRequest(BaseModel):
    contentId: int = Field(gt=0)
    expectedAnalyzedAt: str = Field(min_length=1, max_length=40)


def get_saved_run(db: Session, item_id: str, run_id: str) -> dict:
    stored = db.get(EvaluationRun, run_id)
    if stored and stored.item_id == item_id:
        run = run_response(stored)
    elif run_id in RUNS:
        run = load_run(item_id, run_id)
    elif run_id in REPLAY_RUNS:
        run = load_prompt_replay(item_id, run_id)
    else:
        run = None
    if not run:
        raise HTTPException(404, "해당 영상의 평가 실행을 찾을 수 없습니다.")
    return run


def video_identity(item: EvaluationItem) -> str:
    source = json.loads(item.payload_json)["source"]["url"]
    url = urlsplit(source)
    parts = url.path.strip("/").split("/")
    platform = platform_for_url(source)
    if platform == "INSTAGRAM":
        return "instagram:" + parts[1]
    if url.hostname == "youtu.be":
        video_id = parts[0]
    elif parts[0] == "watch":
        video_id = parse_qs(url.query).get("v", [""])[0]
    elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
        video_id = parts[1]
    else:
        video_id = ""
    if not video_id:
        raise HTTPException(422, "영상 ID를 확인할 수 없습니다.")
    return "youtube:" + video_id


def request_prompt_experiment(path: str, payload: dict) -> dict:
    token = os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "AI 실험 서버가 설정되지 않았습니다.")
    try:
        with httpx.Client(timeout=45, trust_env=False) as client:
            response = client.post(f"{AI_API}/internal/{path}", json=payload, headers={"X-Evaluation-Token": token})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(429, "Gemini 호출 한도에 도달했습니다.") from exc
        raise HTTPException(502, "AI 서버가 프롬프트 실험을 완료하지 못했습니다.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "AI 실험 서버의 응답을 받지 못했습니다.") from exc


class CandidateRequest(BaseModel):
    holdoutItemId: str


@router.get("/prompt-workshop/candidates")
def list_prompt_candidates(db: Session = Depends(get_db)):
    rows = db.scalars(select(PromptCandidate).order_by(PromptCandidate.created_at.desc()).limit(20))
    return [json.loads(row.payload_json) for row in rows]


@router.post("/prompt-workshop/candidates")
def create_prompt_candidate(payload: CandidateRequest, db: Session = Depends(get_db)):
    holdout = find_item(db, payload.holdoutItemId)
    holdout_key = video_identity(holdout)
    reviews = []
    source_keys = set()
    rows = db.execute(select(EvaluationAIDraft, EvaluationItem).join(
        EvaluationItem, EvaluationItem.id == EvaluationAIDraft.item_id).where(
        EvaluationAIDraft.gold_revision == EvaluationItem.revision).order_by(
        EvaluationItem.id, EvaluationAIDraft.run_id))
    for draft, item in rows:
        if json.loads(item.payload_json).get("evaluationStatus") == "EXCLUDED":
            continue
        try:
            key = video_identity(item)
        except (ValueError, HTTPException):
            continue
        if key == holdout_key or key in source_keys:
            continue
        findings = [
            {field: str(finding.get(field, ""))[:350] for field in ("kind", "passage", "explanation", "suggestion")}
            for finding in json.loads(draft.payload_json)["findings"]
            if finding.get("location") == "SUMMARY" and finding.get("kind") in {"INCORRECT", "MISSING", "FORMAT"}
        ]
        if not findings:
            continue
        source_keys.add(key)
        reviews.append({"itemId": item.id, "findings": findings[:6]})
        if len(reviews) == 12:
            break
    if len(reviews) < 2:
        raise HTTPException(409, "이 영상을 제외하고, 서로 다른 영상 2개 이상에 요약 오류가 잡힌 AI 평가 초안이 필요합니다.")
    result = request_prompt_experiment("suggest-prompt-examples", {"reviews": reviews})
    examples = result.get("examples", [])
    if not examples:
        return {"examples": [], "sourceItemIds": [review["itemId"] for review in reviews]}
    candidate = {"id": uuid.uuid4().hex, "model": result.get("model"), "examples": examples,
                 "sourceItemIds": [review["itemId"] for review in reviews], "sourceVideoKeys": sorted(source_keys)}
    db.add(PromptCandidate(id=candidate["id"], payload_json=json.dumps(candidate, ensure_ascii=False)))
    db.commit()
    return candidate


class PromptComparisonRequest(BaseModel):
    candidateId: str


@router.post("/{item_id}/runs/{run_id}/prompt-comparisons")
def compare_prompt_candidate(item_id: str, run_id: str, payload: PromptComparisonRequest, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    if json.loads(item.payload_json).get("evaluationStatus") == "EXCLUDED":
        raise HTTPException(409, "평가에서 제외된 영상입니다.")
    record = db.get(PromptCandidate, payload.candidateId)
    if record is None:
        raise HTTPException(404, "프롬프트 후보가 없습니다.")
    candidate = json.loads(record.payload_json)
    if item_id in candidate["sourceItemIds"] or video_identity(item) in candidate["sourceVideoKeys"]:
        raise HTTPException(409, "이 영상은 후보를 만드는 데 사용되었습니다. 다른 영상을 선택하세요.")
    run = get_saved_run(db, item_id, run_id)
    evidence = [{**unit, "text": str(unit["text"])[:1000]}
                for unit in run["stt"] + run["ocr"]
                if isinstance(unit, dict) and unit.get("id") and str(unit.get("text") or "").strip()][:200]
    if run["status"] not in {"COMPLETED", "REPLAY"} or not evidence:
        raise HTTPException(409, "저장 근거가 있는 완료 실행을 선택해 주세요.")
    inputs = {"sourceTitle": (run["gemini"]["title"] or "")[:300], "evidence": evidence}
    comparison_id = uuid.uuid4().hex
    run_ids = {}
    for variant, examples in (
        ("prompt_baseline", []),
        ("prompt_candidate", [{name: example[name] for name in ("exampleInput", "exampleOutput")}
                              for example in candidate["examples"]]),
    ):
        result = request_prompt_experiment("replay-prompt", {**inputs, "examples": examples})
        if not isinstance(result.get("structured"), dict) or not isinstance(result.get("summary"), str):
            raise HTTPException(502, "요약 결과 형식이 올바르지 않습니다.")
        result["evaluationConfig"] = {"promptVariant": variant, "comparisonId": comparison_id,
                                      "comparisonCandidateId": candidate["id"], "inputRunId": run_id}
        new_id = uuid.uuid4().hex
        db.add(EvaluationRun(id=new_id, item_id=item_id, status="COMPLETED",
                            snapshot_json=json.dumps(result, ensure_ascii=False),
                            finished_at=datetime.now(timezone.utc)))
        run_ids[variant] = new_id
    db.commit()
    return run_ids


@router.post("/{item_id}/runs/{run_id}/ai-review")
def generate_ai_review(item_id: str, run_id: str, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    run = get_saved_run(db, item_id, run_id)
    summary = (run["gemini"]["summary"] or "").strip()
    if run["status"] not in {"COMPLETED", "REPLAY"} or not summary:
        raise HTTPException(409, "요약이 있는 완료된 실행을 선택해 주세요.")
    key = (item_id, run_id, item.revision)
    saved = db.get(EvaluationAIDraft, key)
    if saved:
        return json.loads(saved.payload_json)
    evidence = [{**unit, "text": str(unit["text"])[:1000]}
                for unit in run["stt"] + run["ocr"]
                if isinstance(unit, dict) and unit.get("id") and str(unit.get("text") or "").strip()]
    if not evidence:
        raise HTTPException(409, "이 실행에는 저장된 STT·OCR 근거가 없습니다.")
    token = os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "AI 평가 서버가 설정되지 않았습니다.")
    annotation = json.loads(item.payload_json)
    try:
        with httpx.Client(timeout=45, trust_env=False) as client:
            response = client.post(f"{AI_API}/internal/review-summary", headers={"X-Evaluation-Token": token}, json={
                "summary": summary[:4000],
                "evidence": evidence[:200],
                "goldReference": json.dumps(annotation.get("gold", {}), ensure_ascii=False)[:8000],
                "goldStatus": str(annotation.get("annotation", {}).get("status") or "DRAFT")[:50],
            })
            response.raise_for_status()
            draft = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(429, "Gemini 호출 한도에 도달했습니다. 나중에 다시 시도해 주세요.") from exc
        raise HTTPException(502, "AI 평가 결과를 가져오지 못했습니다.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "AI 평가 서버에 연결하거나 응답을 읽지 못했습니다.") from exc
    if not isinstance(draft, dict) or not isinstance(draft.get("findings"), list):
        raise HTTPException(502, "AI 평가 응답 형식이 올바르지 않습니다.")
    db.add(EvaluationAIDraft(item_id=item_id, run_id=run_id, gold_revision=key[2],
                            payload_json=json.dumps(draft, ensure_ascii=False)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(EvaluationAIDraft, key)
        if existing is None:
            raise
        return json.loads(existing.payload_json)
    return draft


class RevisionRequest(BaseModel):
    mode: Literal["manual", "feedback"]
    feedback: str = Field(default="", max_length=2000)
    desiredSummary: str = Field(default="", max_length=4000)


@router.post("/{item_id}/runs/{run_id}/revisions", status_code=status.HTTP_202_ACCEPTED)
def create_revision(item_id: str, run_id: str, payload: RevisionRequest,
                    background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    parent = get_saved_run(db, item_id, run_id)
    if parent["status"] not in {"COMPLETED", "REPLAY"}:
        raise HTTPException(409, "완료된 실행을 선택해 주세요.")
    feedback, desired = payload.feedback.strip(), payload.desiredSummary.strip()
    if (payload.mode == "manual" and not desired) or not (feedback or desired):
        raise HTTPException(422, "검토 의견 또는 수정할 요약을 입력해 주세요.")
    evidence = [unit for unit in parent["stt"] + parent["ocr"]
                if isinstance(unit, dict) and unit.get("id") and str(unit.get("text") or "").strip()]
    if payload.mode == "feedback" and not evidence:
        raise HTTPException(409, "선택한 실행에 저장된 STT·OCR 근거가 없습니다. 근거가 있는 실행을 선택해 주세요.")
    if payload.mode == "feedback" and not os.getenv("SAVEON_EVALUATION_PUBLISH_TOKEN", "").strip():
        raise HTTPException(503, "검토 의견으로 재요약하는 서버가 설정되지 않았습니다.")

    manual = payload.mode == "manual"
    variant = "manual_edit" if manual else "review_guided"
    config = {"promptVariant": variant, "parentRunId": run_id, "goldRevision": item.revision,
              "feedback": feedback, "desiredSummary": desired}
    snapshot = {"evaluationConfig": config}
    if manual:
        snapshot.update(title=parent["gemini"]["title"], summary=desired, structuredAnalysis={
            "videoEvidence": evidence, "verificationStatus": "NOT_RUN", "summarySource": "MANUAL_EVALUATION",
        })
    run = EvaluationRun(id=uuid.uuid4().hex, item_id=item_id, active_item=None if manual else item_id,
                        status="COMPLETED" if manual else "PENDING",
                        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                        finished_at=datetime.now(timezone.utc) if manual else None)
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이 영상의 분석이 이미 진행 중입니다.")
    if not manual:
        revision_input = {
            "sourceTitle": (parent["gemini"]["title"] or "")[:300],
            "previousSummary": (parent["gemini"]["summary"] or "")[:4000],
            "feedback": feedback,
            "desiredSummary": desired,
            "evidence": [{**unit, "text": str(unit["text"])[:1000]} for unit in evidence[:200]],
        }
        background_tasks.add_task(execute_evaluation_run, run.id, "", variant, revision_input)
    return run_response(run)


@router.put("/{item_id}/runs/{run_id}/publication")
def publish_run(item_id: str, run_id: str, payload: PublicationRequest, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    run = get_saved_run(db, item_id, run_id)
    output = run["gemini"]
    if (run["status"] not in {"COMPLETED", "REPLAY"} or not (output["summary"] or "").strip()
            or output["structured"].get("analysisQuality") == "FALLBACK"):
        raise HTTPException(409, "반영할 수 있는 완료된 요약이 없습니다.")
    return publication_request("PUT", f"/{payload.contentId}", json={
        "sourceUrl": json.loads(item.payload_json)["source"]["url"],
        "summary": output["summary"],
        "structured": output["structured"],
        "expectedAnalyzedAt": payload.expectedAnalyzedAt,
    })


class ReviewUpdate(BaseModel):
    revision: int = Field(ge=0)
    goldRevision: int = Field(ge=1)
    judgments: dict[str, str]
    notes: str = Field(default="", max_length=10000)


@router.put("/{item_id}/reviews/{run_id}")
def save_review(item_id: str, run_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)):
    item = find_item(db, item_id)
    if payload.goldRevision != item.revision:
        raise HTTPException(409, "정답이 변경되었습니다. 다시 불러와 검토해 주세요.")
    live_run = db.get(EvaluationRun, run_id)
    if not ((live_run and live_run.item_id == item_id) or (run_id in RUNS and load_run(item_id, run_id)) or (run_id in REPLAY_RUNS and load_prompt_replay(item_id, run_id))):
        raise HTTPException(404, "해당 영상의 분석 결과를 찾을 수 없습니다.")
    if any(value not in {"UNREVIEWED", "CORRECT", "MISSING", "INCORRECT", "UNCLEAR"} for value in payload.judgments.values()):
        raise HTTPException(422, "유효하지 않은 검토 상태입니다.")
    content = json.dumps({"judgments": payload.judgments, "notes": payload.notes}, ensure_ascii=False)
    review = db.scalar(select(EvaluationReview).where(EvaluationReview.item_id == item_id, EvaluationReview.run_id == run_id))
    if review is None:
        if payload.revision != 0:
            raise HTTPException(409, "검토 내용이 변경되었습니다. 다시 불러와 주세요.")
        review = EvaluationReview(id=uuid.uuid4().hex, item_id=item_id, run_id=run_id, gold_revision=item.revision,
                                  revision=1, payload_json=content)
        db.add(review)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "검토 내용이 변경되었습니다. 다시 불러와 주세요.")
    else:
        changed = db.execute(update(EvaluationReview).where(EvaluationReview.id == review.id, EvaluationReview.revision == payload.revision)
            .values(payload_json=content, gold_revision=item.revision, revision=EvaluationReview.revision + 1, updated_at=datetime.now(timezone.utc)))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "검토 내용이 변경되었습니다. 다시 불러와 주세요.")
        db.commit()
    return {"saved": True}
