import unittest
from services.comparison_grounding import ground_comparison_results


class V7ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.contexts = [
            {"contentId": 21, "title": "클리오 쿠션 8시간 지속력 다크닝 테스트",
             "summary": "8시간 지속력과 다크닝을 테스트한 영상입니다.", "keywords": ["지속력", "다크닝"]},
            {"contentId": 23, "title": "클리오 쿠션 메쉬 블러 런칭",
             "summary": "모공을 블러리하게 표현하는 쿠션입니다.", "keywords": ["모공", "블러"]},
            {"contentId": 20, "title": "클리오 쿠션 모공 블러 사용 팁",
             "summary": "모공 커버를 위한 얇은 레이어링과 브러시 사용 팁입니다.", "keywords": ["모공", "블러", "브러시"]},
        ]

    def test_same_pair_topics_deduplicated(self):
        result = ground_comparison_results({"comparisonEntity":"클리오"}, self.contexts,
                                           fallback_when_empty=True, comparison_entity="클리오")
        self.assertEqual(len(result["commonPoints"]), 1)
        self.assertEqual({ev["contentId"] for ev in result["commonPoints"][0]["evidences"]}, {20, 23})
        self.assertIn("평가가 같은지는 확인되지", result["commonPoints"][0]["statement"])

    def test_video_specific_highlights_are_short_and_source_backed(self):
        result = ground_comparison_results({}, self.contexts, fallback_when_empty=True)
        unique = result["uniqueMentions"]
        self.assertEqual(len(unique), 3)
        self.assertEqual({x["evidences"][0]["contentId"] for x in unique}, {20,21,23})
        for x in unique:
            self.assertLess(len(x["statement"]), 100)
            self.assertIn("원본 영상 검증 전", x["statement"])
            context = next(c for c in self.contexts if c["contentId"] == x["evidences"][0]["contentId"])
            self.assertTrue(x["evidences"][0]["quote"] in context["summary"] or x["evidences"][0]["quote"] in context["title"])

    def test_repeated_model_common_statement_deduplicated(self):
        ctx = [{"contentId":1,"title":"영상 1","summary":"수분감이 좋아서 만족했어요."},
               {"contentId":2,"title":"영상 2","summary":"수분감이 좋아서 만족했어요."}]
        evidence = [{"contentId":1,"quote":"수분감이 좋아서 만족했어요."},
                    {"contentId":2,"quote":"수분감이 좋아서 만족했어요."}]
        common = {"topic":"수분감","statement":"수분감이 좋다고 평가합니다.","evidences":evidence}
        result = ground_comparison_results({"commonPoints":[common,common]}, ctx,
                    semantic_audit=lambda checks:{c["key"]:True for c in checks})
        self.assertEqual(len(result["commonPoints"]),1)

    def test_no_unfounded_shared_quality(self):
        result = ground_comparison_results({}, self.contexts, fallback_when_empty=True)
        self.assertFalse(any("뛰어나다" in x["statement"] or "5가지" in x["statement"] for x in result["commonPoints"]))

    def test_disagreement_kept_when_joint_audit_approves(self):
        contexts = [{"contentId":1,"summary":"지속력이 좋았어요."},
                    {"contentId":2,"summary":"지속력이 좋지 않았어요."}]
        finding = {"topic":"지속력","statement":"지속력에 대한 평가가 엇갈려요.",
                   "evidences":[{"contentId":1,"quote":"지속력이 좋았어요."},
                                {"contentId":2,"quote":"지속력이 좋지 않았어요."}]}
        r=ground_comparison_results({"disagreements":[finding]},contexts,
                   semantic_audit=lambda checks:{c["key"]:True for c in checks},fallback_when_empty=True)
        self.assertEqual(len(r["disagreements"]),1)

if __name__ == '__main__': unittest.main()
