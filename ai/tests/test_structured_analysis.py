import unittest
from unittest.mock import patch

from services.embedding_service import _normalize
from services.llm_postprocessor import _normalize_result
from services.verified_summary import (
    _compact_fact_checks,
    _verification_status,
    apply_verified_summary,
)


class StructuredAnalysisTests(unittest.TestCase):
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
            "claims": [{"verifiable": True}],
            "factChecks": [{"verdict": "SUPPORTED"}],
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
