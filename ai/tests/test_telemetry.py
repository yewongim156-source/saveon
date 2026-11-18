import unittest
from unittest.mock import patch

from services.telemetry import pipeline_step, trace_session


class TelemetryTests(unittest.TestCase):
    def test_trace_and_step_emit_ordered_events_without_raw_url(self):
        events = []

        with patch(
            "services.telemetry.CLIENT.emit",
            side_effect=events.append,
        ):
            with trace_session(
                platform="YOUTUBE",
                source_url="https://youtube.com/shorts/private-id",
            ):
                with pipeline_step(
                    "content-structuring",
                    kind="AGENT",
                    model="gemini-test",
                ) as step:
                    step.set_output({"category": "장소/여행"})

        self.assertEqual(
            [event["eventType"] for event in events],
            [
                "TRACE_STARTED",
                "STEP_STARTED",
                "STEP_FINISHED",
                "TRACE_FINISHED",
            ],
        )
        self.assertNotIn(
            "private-id",
            str(events[0]["data"]),
        )
        self.assertEqual(
            events[2]["data"]["outputSummary"]["category"],
            "장소/여행",
        )

    def test_failed_step_does_not_hide_original_error(self):
        events = []

        with patch(
            "services.telemetry.CLIENT.emit",
            side_effect=events.append,
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                with trace_session(platform="UPLOAD"):
                    with pipeline_step("ocr", kind="TOOL"):
                        raise RuntimeError("boom")

        self.assertIn(
            "STEP_FAILED",
            [event["eventType"] for event in events],
        )
        self.assertEqual(events[-1]["eventType"], "TRACE_FAILED")


if __name__ == "__main__":
    unittest.main()
