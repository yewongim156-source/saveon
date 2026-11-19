import os
import unittest
from pathlib import Path
from unittest.mock import patch

from services import overlay_vision as ov


def unit(i, text, time_ms):
    return {"id": f"ocr-{i:03d}", "text": text, "timeMs": time_ms, "modality": "OCR"}


class OverlayVisionTests(unittest.TestCase):
    def test_frames_with_prices_or_amounts_are_chosen_and_spread_apart(self):
        timed = [
            unit(1, "서울숲 산책", 1000),
            unit(2, "27,000원", 33000), unit(3, "기돈 스트라이프", 33000),
            unit(4, "₩38,750", 4400), unit(5, "상품명", 4400), unit(6, "8,300원", 4400),
            unit(7, "6,400원", 4900),               # within 1.5s of 4400: skipped
            unit(8, "간장 1스푼", 14700), unit(9, "설탕 0.5스푼", 14700),
        ]
        self.assertEqual(ov.select_overlay_times(timed, max_frames=3), [4400, 14700, 33000])
        self.assertEqual(ov.select_overlay_times(timed, max_frames=1), [4400])
        self.assertEqual(ov.select_overlay_times([unit(1, "그냥 자막", 0)]), [])

    def test_vision_lines_replace_the_noisy_ocr_of_the_same_frame_only(self):
        timed = [unit(1, "앞 장면", 1000), unit(2, "기돈 스트라이프 티서츠", 33000), unit(3, "27,000원", 33000),
                 unit(4, "뒤 장면", 40000)]
        with patch.dict(os.environ, {"OCR_VISION_REFINE": "true"}), patch.object(ov, "GEMINI_API_KEY", "k"), \
                patch.object(ov, "grab_frame", return_value=object()), \
                patch.object(ov, "read_overlay_text", return_value=["히어썸웨어", "이든 스트라이프 티셔츠", "₩27,000"]):
            refined, stats = ov.refine_overlay_ocr(Path("x.mp4"), timed)
        self.assertEqual([u["text"] for u in refined],
                         ["앞 장면", "히어썸웨어", "이든 스트라이프 티셔츠", "₩27,000", "뒤 장면"])
        self.assertEqual([u["id"] for u in refined], [f"ocr-{i:03d}" for i in range(1, 6)])
        self.assertEqual(refined[1]["source"], "gemini-vision")
        self.assertNotIn("source", refined[0])
        self.assertEqual(stats, {"candidateFrames": 1, "refinedFrames": 1, "failedFrames": 0})

    def test_failure_or_disabled_keeps_the_original_ocr(self):
        timed = [unit(1, "기돈 스트라이프", 33000), unit(2, "27,000원", 33000)]
        with patch.dict(os.environ, {"OCR_VISION_REFINE": "true"}), patch.object(ov, "GEMINI_API_KEY", "k"), \
                patch.object(ov, "grab_frame", return_value=object()), \
                patch.object(ov, "read_overlay_text", side_effect=RuntimeError("503")):
            refined, stats = ov.refine_overlay_ocr(Path("x.mp4"), timed)
        self.assertEqual(refined, timed)
        self.assertEqual(stats["failedFrames"], 1)
        with patch.dict(os.environ, {"OCR_VISION_REFINE": "false"}), patch.object(ov, "read_overlay_text") as read:
            refined, _ = ov.refine_overlay_ocr(Path("x.mp4"), timed)
        read.assert_not_called()
        self.assertEqual(refined, timed)


if __name__ == "__main__":
    unittest.main()
