from __future__ import annotations

import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


_TEMP_DIR = tempfile.TemporaryDirectory(prefix="saveon-developer-test-")
_DB_PATH = Path(_TEMP_DIR.name) / "developer.db"
os.environ["DEVELOPER_DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"

from fastapi.testclient import TestClient

from database import Base, engine
from main import app


class DeveloperApiTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        _TEMP_DIR.cleanup()

    def _event(self, event_type: str, **overrides):
        payload = {
            "eventId": overrides.pop("eventId", f"event-{event_type}"),
            "traceId": "trace-1",
            "stepId": overrides.pop("stepId", None),
            "eventType": event_type,
            "occurredAt": "2026-10-29T01:00:00Z",
            "data": overrides.pop("data", {}),
        }
        payload.update(overrides)
        return payload

    def test_evaluation_edit_persists_and_detects_stale_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evaluation").mkdir()
            (root / "evaluation" / "pilot_v1.json").write_text(json.dumps({"items": [{"id": "pilot-002", "source": {"url": "https://example.com"}, "gold": {"mainTopic": "초안"}, "annotation": {"status": "DRAFT"}}]}), encoding="utf-8")
            with patch("evaluation_api.ROOT", root):
                item = self.client.get("/admin/evaluations").json()[0]
                body = {"revision": item["revision"], "gold": {"mainTopic": "수정"}, "annotation": {"status": "REVIEWED"}}
                self.assertEqual(self.client.put("/admin/evaluations/pilot-002", json=body).status_code, 200)
                self.assertEqual(self.client.put("/admin/evaluations/pilot-002", json=body).status_code, 409)
                self.assertEqual(self.client.get("/admin/evaluations").json()[0]["item"]["gold"]["mainTopic"], "수정")
                self.assertEqual(self.client.get("/admin/evaluations/pilot-002").json()["runs"], [])

    def test_evaluation_displays_only_evidence_from_selected_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evaluation").mkdir()
            (root / "evaluation" / "user_sources.json").write_text(json.dumps({"sources": [{"id": "user-001", "url": "https://example.com"}]}), encoding="utf-8")
            run_dir = root / ".runtime" / "grounding-replay"
            run_dir.mkdir(parents=True)
            (run_dir / "user-001.json").write_text(json.dumps({"summary": "요약", "structured": {"videoEvidence": [{"id": "s", "modality": "STT", "text": "음성"}, {"id": "o", "modality": "OCR", "text": "자막"}]}}), encoding="utf-8")
            with patch("evaluation_api.ROOT", root):
                self.client.get("/admin/evaluations")
                run = self.client.get("/admin/evaluations/user-001").json()["runs"][0]
                self.assertEqual([x["id"] for x in run["stt"]], ["s"])
                self.assertEqual([x["id"] for x in run["ocr"]], ["o"])
                self.assertEqual(run["gemini"]["summary"], "요약")

    def test_add_video_and_run_until_completed(self):
        created = self.client.post("/admin/evaluations", json={"url": "https://www.youtube.com/shorts/waqvnBsCyHA", "title": "제품"})
        self.assertEqual(created.status_code, 201)
        item_id = created.json()["item"]["id"]
        self.assertEqual(created.json()["item"]["annotation"]["status"], "DRAFT")
        with patch("evaluation_api.httpx.Client") as client:
            session = client.return_value.__enter__.return_value
            session.post.return_value.json.return_value = {"title": "영상", "summary": "정리", "structured": {"videoEvidence": [{"modality": "STT", "text": "음성"}]}}
            started = self.client.post(f"/admin/evaluations/{item_id}/runs")
            self.assertEqual(started.status_code, 202)
            run_id = started.json()["id"]
            self.assertTrue(session.post.call_args.args[0].endswith('/analyze'))
            self.assertNotIn('/contents', session.post.call_args.args[0])
            self.assertEqual(session.post.call_args.kwargs['json']['promptVariant'], 'baseline')
            finished = self.client.post(f"/admin/evaluations/{item_id}/runs/{run_id}/refresh")
            self.assertEqual(finished.json()["status"], "COMPLETED")
            self.assertEqual(finished.json()["stt"][0]["text"], "음성")
            self.assertEqual(self.client.get(f"/admin/evaluations/{item_id}").json()["runs"][0]["gemini"]["summary"], "정리")
            self.assertEqual(self.client.post(f"/admin/evaluations/{item_id}/runs").status_code, 202)

    def test_few_shot_variant_is_recorded_and_passed_to_ai(self):
        item = self.client.post("/admin/evaluations", json={"url": "https://youtu.be/abc"}).json()["item"]
        with patch("evaluation_api.httpx.Client") as client:
            session = client.return_value.__enter__.return_value
            session.post.return_value.json.return_value = {"summary": "예시", "structured": {}}
            response = self.client.post(f"/admin/evaluations/{item['id']}/runs", json={"promptVariant": "few_shot_v1"})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(session.post.call_args.kwargs['json']['promptVariant'], 'few_shot_v1')
            run = self.client.get(f"/admin/evaluations/{item['id']}").json()["runs"][0]
            self.assertIn("few_shot_v1", run["label"])
            self.assertEqual(run["status"], "COMPLETED")

    def test_invalid_urls_and_submission_failure(self):
        self.assertEqual(self.client.post("/admin/evaluations", json={"url": "http://youtube.com.evil.test/a"}).status_code, 422)
        self.assertEqual(self.client.post("/admin/evaluations", json={"url": "https://instagram.com/reel/abc/"}).status_code, 201)
        item = self.client.post("/admin/evaluations", json={"url": "https://youtu.be/abc"}).json()["item"]
        import httpx
        with patch("evaluation_api.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("unavailable")
            result = self.client.post(f"/admin/evaluations/{item['id']}/runs").json()
            self.assertEqual(result["status"], "PENDING")
            saved = self.client.get(f"/admin/evaluations/{item['id']}").json()["runs"][0]
            self.assertEqual(saved["status"], "FAILED")

    def test_review_is_saved_per_run_and_marks_changed_gold_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evaluation").mkdir()
            (root / "evaluation" / "user_sources.json").write_text(json.dumps({"sources": [{"id": "user-001", "url": "https://youtu.be/test"}]}), encoding="utf-8")
            run_dir = root / ".runtime" / "user-pilot-results"
            run_dir.mkdir(parents=True)
            (run_dir / "user-001.json").write_text(json.dumps({"content": {"status": "COMPLETED", "summary": "결과"}}), encoding="utf-8")
            with patch("evaluation_api.ROOT", root):
                self.client.get("/admin/evaluations")
                body = {"revision": 0, "goldRevision": 1, "judgments": {"targets/0/name": "MISSING"}, "notes": "제품 누락"}
                url = "/admin/evaluations/user-001/reviews/baseline"
                self.assertEqual(self.client.put(url, json=body).status_code, 200)
                self.assertEqual(self.client.put(url, json=body).status_code, 409)
                detail = self.client.get("/admin/evaluations/user-001").json()
                self.assertEqual(detail["reviews"]["baseline"]["data"]["judgments"]["targets/0/name"], "MISSING")
                self.assertFalse(detail["reviews"]["baseline"]["stale"])
                self.client.put("/admin/evaluations/user-001", json={"revision": 1, "gold": {"mainTopic": "변경"}, "annotation": {"status": "DRAFT"}})
                self.assertTrue(self.client.get("/admin/evaluations/user-001").json()["reviews"]["baseline"]["stale"])
                self.assertEqual(self.client.put(url, json={**body, "revision": 1}).status_code, 409)
                self.assertEqual(self.client.put("/admin/evaluations/user-001/reviews/unknown", json={**body, "goldRevision": 2}).status_code, 404)

    def test_ingests_trace_and_step_events(self):
        response = self.client.post(
            "/internal/events",
            json=self._event(
                "TRACE_STARTED",
                data={"platform": "YOUTUBE", "sourceHash": "abc"},
            ),
        )
        self.assertEqual(response.status_code, 202)

        response = self.client.post(
            "/internal/events",
            json=self._event(
                "STEP_STARTED",
                eventId="event-step-started",
                stepId="step-1",
                data={
                    "kind": "AGENT",
                    "name": "content-structuring",
                    "model": "gemini-test",
                },
            ),
        )
        self.assertEqual(response.status_code, 202)

        response = self.client.post(
            "/internal/events",
            json=self._event(
                "STEP_FINISHED",
                eventId="event-step-finished",
                stepId="step-1",
                data={
                    "durationMs": 120,
                    "outputSummary": {"category": "장소/여행"},
                    "inputTokens": 100,
                    "outputTokens": 30,
                    "estimatedCostUsd": 0.001,
                },
            ),
        )
        self.assertEqual(response.status_code, 202)

        response = self.client.post(
            "/internal/events",
            json=self._event(
                "TRACE_FINISHED",
                eventId="event-trace-finished",
                data={"durationMs": 250},
            ),
        )
        self.assertEqual(response.status_code, 202)

        detail = self.client.get("/admin/traces/trace-1")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["status"], "COMPLETED")
        self.assertEqual(body["stepCount"], 1)
        self.assertEqual(body["steps"][0]["kind"], "AGENT")
        self.assertAlmostEqual(body["totalCostUsd"], 0.001)

        overview = self.client.get("/admin/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["totalSessions"], 1)
        self.assertEqual(overview.json()["totalSteps"], 1)

    def test_duplicate_event_is_idempotent(self):
        event = self._event(
            "TRACE_STARTED",
            eventId="event-duplicate",
            traceId="trace-duplicate",
        )
        first = self.client.post("/internal/events", json=event)
        second = self.client.post("/internal/events", json=event)

        self.assertFalse(first.json()["duplicate"])
        self.assertTrue(second.json()["duplicate"])

    def test_admin_routes_can_require_internal_token(self):
        with patch.dict(
            os.environ,
            {"DEVELOPER_API_TOKEN": "test-secret"},
        ):
            denied = self.client.get("/admin/overview")
            allowed = self.client.get(
                "/admin/overview",
                headers={"X-Developer-Token": "test-secret"},
            )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
