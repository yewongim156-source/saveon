from __future__ import annotations

import os
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
