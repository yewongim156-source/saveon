import unittest

from services.comparison_grounding import ground_comparison_results


class SourceOnlyFallbackTests(unittest.TestCase):
    def setUp(self):
        self.contexts = [
            {"contentId": 21, "title": "클리오 쿠션 지속력 테스트", "summary": "8시간 지속력과 다크닝을 확인하는 영상입니다."},
            {"contentId": 23, "title": "클리오 쿠션 신상 런칭", "summary": "메쉬 블러 쿠션의 런칭 소식과 모공 표현을 소개합니다."},
            {"contentId": 20, "title": "클리오 쿠션 사용 팁", "summary": "얇게 레이어링하고 브러시로 바르는 방법을 소개합니다."},
        ]

    def test_no_approved_claims_shows_source_only_highlights(self):
        raw = {
            "title": "비교 결과", "summary": "검증 전 생성된 과장된 AI 요약",
            "commonPoints": [{"topic": "성능", "statement": "커버력이 탁월합니다", "evidences": [
                {"contentId": 21, "quote": "허구의 증거"},
                {"contentId": 23, "quote": "허구의 증거"},
            ]}],
            "disagreements": [], "uniqueMentions": [],
        }
        result = ground_comparison_results(raw, self.contexts,
                                           semantic_audit=lambda _: {},
                                           fallback_when_empty=True)
        self.assertEqual(result["commonPoints"], [])
        self.assertEqual(result["disagreements"], [])
        self.assertEqual(len(result["uniqueMentions"]), 3)
        self.assertEqual({x["evidences"][0]["contentId"] for x in result["uniqueMentions"]}, {20,21,23})
        for item in result["uniqueMentions"]:
            self.assertIn("원본 영상 검증 전", item["statement"])
            evidence = item["evidences"][0]
            source = next(ctx for ctx in self.contexts if ctx["contentId"] == evidence["contentId"])
            self.assertTrue(evidence["quote"] in source["summary"] or evidence["quote"] in source["title"])
            self.assertIsNone(evidence["timestampSeconds"])

    def test_fallback_disabled_by_default(self):
        result = ground_comparison_results({}, self.contexts, semantic_audit=lambda _: {})
        self.assertEqual(result["uniqueMentions"], [])

    def test_no_fallback_if_valid_result_exists(self):
        contexts = [{"contentId": 20, "title": "클리오 쿠션 리뷰", "summary": "모공 커버를 소개합니다."}]
        raw = {"uniqueMentions": [{"topic": "관련", "statement": "모공 커버", "evidences": [
            {"contentId": 20, "quote": "모공 커버를 소개합니다."}
        ]}]}
        result = ground_comparison_results(raw, contexts,
                                           semantic_audit=lambda checks: {x["key"]: True for x in checks},
                                           fallback_when_empty=True)
        self.assertEqual(len(result["uniqueMentions"]), 1)
        self.assertNotIn("원본 영상 검증 전", result["uniqueMentions"][0]["statement"])

    def test_fallback_avoids_garbage_metadata(self):
        contexts = [{"contentId": 19, "title": "Video by xy", "summary": "", "entities": ["'O", "[Ie"]},
                    {"contentId": 20, "title": "클리오 쿠션 사용 방법", "summary": ""}]
        result = ground_comparison_results({}, contexts, fallback_when_empty=True)
        self.assertEqual(len(result["uniqueMentions"]), 1)
        self.assertEqual(result["uniqueMentions"][0]["evidences"][0]["contentId"], 20)

    def test_duplicate_content_ids_only_once(self):
        contexts = self.contexts + [self.contexts[0]]
        result = ground_comparison_results({}, contexts, fallback_when_empty=True)
        self.assertEqual(len(result["uniqueMentions"]), 3)


if __name__ == "__main__":
    unittest.main()
