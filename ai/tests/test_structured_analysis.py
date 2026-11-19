import unittest
from unittest.mock import patch

from services.embedding_service import _normalize
from services.llm_postprocessor import _normalize_result
from services.verified_summary import (
    _compact_fact_checks,
    _verification_status,
    apply_verified_summary,
)
from services.video_pipeline import build_categories, build_summary, run_timed_ocr


class StructuredAnalysisTests(unittest.TestCase):
    def test_target_and_global_steps_are_rendered_together(self):
        evidence = [{"id": "ocr-1"}]
        step = lambda text: {"text": text, "evidenceIds": ["ocr-1"]}
        result = _normalize_result({
            "targets": [
                {"name": "요리 A", "nameEvidenceIds": ["ocr-1"],
                 "steps": [step("재료를 썬다"), step("재료를 볶는다")]},
                {"name": "요리 B", "nameEvidenceIds": ["ocr-1"],
                 "details": [step("차갑게 먹는 요리")]},
            ],
            "globalSteps": [step("완성한 두 요리를 함께 담는다")],
        }, evidence)
        self.assertEqual(result["summary"], (
            "요리 A\n1. 재료를 썬다\n2. 재료를 볶는다\n\n"
            "요리 B\n- 차갑게 먹는 요리\n\n"
            "전체 순서\n1. 완성한 두 요리를 함께 담는다"
        ))

    def test_v2_summary_drops_details_that_repeat_a_step(self):
        evidence = [{"id": "stt-1"}]
        item = lambda text: {"text": text, "evidenceIds": ["stt-1"]}
        target = {
            "name": "소시지 덮밥", "nameEvidenceIds": ["stt-1"], "type": "RECIPE",
            "details": [item("버터에 소시지를 굽는다"), item("간장 1스푼, 설탕 0.5스푼")],
            "steps": [item("소시지를 버터에 굽는다"), item("밥 위에 올린다")],
        }
        plain = _normalize_result({"targets": [target]}, evidence)
        deduped = _normalize_result({"targets": [target]}, evidence, dedupe_details=True)
        self.assertIn("- 버터에 소시지를 굽는다", plain["summary"])
        self.assertNotIn("- 버터에 소시지를 굽는다", deduped["summary"])
        self.assertIn("- 간장 1스푼, 설탕 0.5스푼", deduped["summary"])
        self.assertEqual(len(deduped["structured"]["targets"][0]["details"]), 2)

    def test_strict_drops_prices_not_found_in_cited_units(self):
        evidence = [{"id": "ocr-1", "text": "438750"}, {"id": "ocr-2", "text": "드무어 에피 딥브이니트"}]
        target = {
            "name": "드무어 에피 딥브이 니트", "nameEvidenceIds": ["ocr-2"], "type": "PRODUCT",
            "details": [
                {"text": "영상 표시 가격 38,750원", "evidenceIds": ["ocr-1"]},
                {"text": "영상 표시 가격 43,750원", "evidenceIds": ["ocr-1"]},
                {"text": "명치까지 내려오는 V넥", "evidenceIds": ["ocr-2"]},
            ],
            "steps": [],
        }
        loose = _normalize_result({"targets": [target]}, evidence)
        strict = _normalize_result({"targets": [target]}, evidence, strict=True)
        self.assertEqual(len(loose["structured"]["targets"][0]["details"]), 3)
        texts = [detail["text"] for detail in strict["structured"]["targets"][0]["details"]]
        self.assertEqual(texts, ["영상 표시 가격 38,750원", "명치까지 내려오는 V넥"])

    def test_strict_labels_promotional_details_and_uses_neutral_source_title(self):
        evidence = [{"id": "stt-1", "text": "헬스장보다 더한 효과"}]
        target = {
            "name": "홈트", "nameEvidenceIds": ["stt-1"], "type": "WORKOUT",
            "details": [{"text": "효과가 보장되는 운동", "evidenceIds": ["stt-1"]}], "steps": [],
        }
        payload = {"title": "헬스장보다 확실한 홈트 모음", "targets": [target]}
        loose = _normalize_result(payload, evidence, source_title="인생 홈트 모음집")
        strict = _normalize_result(payload, evidence, source_title="인생 홈트 모음집", strict=True)
        self.assertEqual(loose["title"], "헬스장보다 확실한 홈트 모음")
        self.assertEqual(strict["title"], "인생 홈트 모음집")
        self.assertEqual(strict["structured"]["targets"][0]["details"][0]["text"], "영상 주장: 효과가 보장되는 운동")

    def test_flags_when_fewer_targets_than_announced(self):
        evidence = [{"id": "ocr-1"}]
        target = {"name": "A", "nameEvidenceIds": ["ocr-1"], "type": "PRODUCT", "details": [], "steps": []}
        short = _normalize_result({"announcedItemCount": 6, "targets": [target]}, evidence)
        full = _normalize_result({"announcedItemCount": 1, "targets": [target]}, evidence)
        none = _normalize_result({"targets": [target]}, evidence)
        self.assertEqual((short["structured"]["announcedItemCount"], short["structured"]["itemCountMismatch"]), (6, True))
        self.assertFalse(full["structured"]["itemCountMismatch"])
        self.assertNotIn("itemCountMismatch", none["structured"])

    def test_ocr_keeps_first_timestamp_and_deduplicates(self):
        import numpy as np
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        with patch("services.video_pipeline._get_ocr") as reader:
            reader.return_value.readtext.side_effect = [["제품 A"], ["제품 A", "제품 B"]]
            result = run_timed_ocr([(0, frame), (2000, frame)])
        self.assertEqual(result, [{"id": "ocr-001", "text": "제품 A", "timeMs": 0, "modality": "OCR"}, {"id": "ocr-002", "text": "제품 B", "timeMs": 2000, "modality": "OCR"}])

    def test_keeps_target_details_and_steps(self):
        evidence = [{"id": "stt-001", "text": "제품 A는 가볍다"}]
        result = _normalize_result({
            "categories": ["제품/쇼핑"],
            "targets": [{"name": "제품 A", "nameEvidenceIds": ["stt-001"], "type": "PRODUCT", "details": [{"text": "가벼운 제형", "evidenceIds": ["stt-001"]}, {"text": "없는 정보", "evidenceIds": ["unknown"]}], "steps": []}],
            "globalSteps": [{"text": "준비한다", "evidenceIds": ["unknown"]}],
        }, evidence)
        self.assertEqual(result["structured"]["targets"][0]["details"][0]["evidenceIds"], ["stt-001"])
        self.assertEqual(len(result["structured"]["targets"][0]["details"]), 1)
        self.assertEqual(result["structured"]["globalSteps"], [])
        self.assertEqual(result["summary"], "제품 A\n- 가벼운 제형")
        self.assertEqual(result["structured"]["targets"][0]["verificationStatus"], "NOT_VERIFIED")
        self.assertEqual(result["structured"]["targets"][0]["details"][0]["evidenceStatus"], "VIDEO_ATTRIBUTED_UNVERIFIED")

    def test_keeps_raw_summary_when_search_failed(self):
        result = {"summary": "원본 요약", "structured": {"claims": [{"verifiable": True}], "factChecks": [{"verdict": "INSUFFICIENT_EVIDENCE"}]}}
        with patch("services.verified_summary.FACT_CHECK_ENABLED", True), patch("services.verified_summary._generate_verified_summary") as generate:
            finalized = apply_verified_summary(result)
        generate.assert_not_called()
        self.assertEqual(finalized["summary"], "원본 요약")
        self.assertEqual(finalized["structured"]["verificationStatus"], "INSUFFICIENT_EVIDENCE")

    def test_fallback_does_not_mix_clip_labels_into_transcript_topic(self):
        categories = build_categories(
            "We are standing next to the elephants at the zoo.",
            [],
            ["fashion", "food", "travel"],
            "Me at the zoo",
        )

        self.assertEqual(categories, ["영상"])

    def test_fallback_ignores_description_when_transcript_exists(self):
        summary = build_summary(
            "코끼리 앞에서 짧게 설명하는 영상입니다.",
            [],
            ["fashion", "food"],
            "뇌 속 미세플라스틱에 관한 무관한 홍보 문구",
            "jawed",
        )

        self.assertIn("코끼리", summary)
        self.assertNotIn("미세플라스틱", summary)
        self.assertNotIn("화면 유형", summary)

    def test_normalizes_structured_metadata(self):
        result = _normalize_result({
            "title": "성수 카페",
            "summary": "성수동 카페를 소개합니다.",
            "categories": ["장소/여행"],
            "keywords": ["성수", "카페"],
            "entities": [],
            "primaryCategory": "장소/여행",
            "secondaryCategories": ["카페"],
            "tags": ["성수", "데이트"],
            "contentType": "PLACE_RECOMMENDATION",
            "entityDetails": [
                {
                    "name": "성수역",
                    "type": "PLACE",
                    "confidence": 1.4,
                }
            ],
            "claims": [
                {
                    "text": "성수역에서 도보 5분 거리다",
                    "type": "LOCATION",
                    "verifiable": True,
                    "searchQuery": "카페 성수역 도보 거리",
                    "confidence": 0.8,
                }
            ],
        })

        self.assertEqual(
            result["structured"]["primaryCategory"],
            "장소/여행",
        )
        self.assertEqual(
            result["structured"]["entityDetails"][0]["confidence"],
            1.0,
        )
        self.assertEqual(result["entities"], ["성수역"])
        self.assertEqual(len(result["structured"]["claims"]), 1)

    def test_rejects_unknown_top_level_category(self):
        result = _normalize_result({
            "categories": ["존재하지 않는 카테고리"],
            "primaryCategory": "잘못된 값",
        })

        self.assertEqual(result["categories"], ["기타"])
        self.assertEqual(
            result["structured"]["primaryCategory"],
            "기타",
        )

    def test_embedding_normalization(self):
        vector = _normalize([3.0, 4.0])
        self.assertAlmostEqual(vector[0], 0.6)
        self.assertAlmostEqual(vector[1], 0.8)

    def test_verification_status_requires_enabled_fact_checking(self):
        structured = {
            "claims": [{"text": "주장 A", "verifiable": True}],
            "factChecks": [{"claim": "주장 A", "verdict": "SUPPORTED", "sources": [{"url": "https://example.org"}]}],
        }

        with patch(
            "services.verified_summary.FACT_CHECK_ENABLED",
            False,
        ):
            self.assertEqual(
                _verification_status(structured),
                "NOT_RUN",
            )

        with patch(
            "services.verified_summary.FACT_CHECK_ENABLED",
            True,
        ):
            self.assertEqual(
                _verification_status(structured),
                "VERIFIED",
            )

    def test_partial_checks_cannot_verify_all_claims(self):
        structured = {
            "claims": [{"text": "주장 A", "verifiable": True}, {"text": "주장 B", "verifiable": True}],
            "factChecks": [{"claim": "주장 A", "verdict": "SUPPORTED", "sources": [{"url": "https://example.org"}]}],
        }
        with patch("services.verified_summary.FACT_CHECK_ENABLED", True):
            self.assertEqual(_verification_status(structured), "PARTIALLY_VERIFIED")

    def test_unrelated_or_sourceless_checks_do_not_verify_claim(self):
        structured = {
            "claims": [{"text": "주장 A", "verifiable": True}],
            "factChecks": [{"claim": "주장 B", "verdict": "SUPPORTED", "sources": [{"url": "https://example.org"}]}],
        }
        with patch("services.verified_summary.FACT_CHECK_ENABLED", True):
            self.assertEqual(_verification_status(structured), "INSUFFICIENT_EVIDENCE")
            structured["factChecks"][0] = {"claim": "주장 A", "verdict": "SUPPORTED", "sources": []}
            self.assertEqual(_verification_status(structured), "INSUFFICIENT_EVIDENCE")

    def test_compacts_sources_without_losing_fact_check_index(self):
        compact = _compact_fact_checks({
            "factChecks": [
                {
                    "claim": "행사는 5월 1일 열린다",
                    "verdict": "SUPPORTED",
                    "explanation": "공식 일정과 일치한다.",
                    "sources": [
                        {
                            "title": "공식 일정",
                            "url": "https://example.com/event",
                        }
                    ],
                }
            ]
        })

        self.assertEqual(compact[0]["factCheckIndex"], 0)
        self.assertEqual(
            compact[0]["sources"][0]["url"],
            "https://example.com/event",
        )

    def test_keeps_raw_summary_when_verification_did_not_run(self):
        result = {
            "summary": "영상에서 소개한 원래 요약",
            "structured": {
                "claims": [],
                "factChecks": [],
            },
        }

        with patch(
            "services.verified_summary.FACT_CHECK_ENABLED",
            False,
        ):
            finalized = apply_verified_summary(result)

        self.assertEqual(
            finalized["summary"],
            "영상에서 소개한 원래 요약",
        )
        self.assertEqual(
            finalized["structured"]["verificationStatus"],
            "NOT_RUN",
        )
        self.assertEqual(
            finalized["structured"]["summarySource"],
            "RAW_ANALYSIS",
        )


if __name__ == "__main__":
    unittest.main()
