import unittest

from services.comparison_grounding import ground_comparison_results


def evidence(cid, quote):
    return {"contentId": cid, "title": f"영상 {cid}", "quote": quote,
            "timestampSeconds": 987.0}


def finding(statement, *items):
    return {"topic": "제품 비교", "statement": statement,
            "evidences": [evidence(*x) for x in items]}


def admit_all(checks):
    return {x["key"]: True for x in checks}


class SavedComparisonEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.contexts = [
            {"contentId": 20, "title": "클리오 쿠션 솔직 리뷰", "summary": "브러시 사용 팁을 소개합니다.",
             "entities": ["클리오"]},
            {"contentId": 21, "title": "클리오 쿠션 전컬러 발색 리뷰", "summary": "전컬러 발색 리뷰",
             "entities": ["KRW 36000"]},
            {"contentId": 23, "title": "클리오 메쉬 블러 쿠션", "summary": "컬러 하나 다섯 가지로 출시되었어요.",
             "entities": ["클리오"]},
        ]

    def ground(self, payload, auditor=admit_all):
        return ground_comparison_results(payload, self.contexts, semantic_audit=auditor)

    def test_quantity_not_supported_by_every_source_demotes_to_single_video(self):
        raw = {"commonPoints": [finding("쿠션은 총 5가지 컬러로 출시되었어요.",
                  (21, "전컬러 발색 리뷰"), (23, "컬러 하나 다섯 가지로 출시되었어요."))]}
        result = self.ground(raw)
        self.assertEqual(result["commonPoints"], [])
        self.assertEqual(len(result["uniqueMentions"]), 1)
        self.assertEqual(result["uniqueMentions"][0]["evidences"][0]["contentId"], 23)
        self.assertIn("다섯 가지", result["uniqueMentions"][0]["statement"])

    def test_application_tip_does_not_prove_excellence(self):
        raw = {"commonPoints": [finding("모공 커버력이 뛰어난 제품입니다.",
                     (20, "브러시 사용 팁을 소개합니다."),
                     (23, "컬러 하나 다섯 가지로 출시되었어요."))]}
        result = self.ground(raw)
        self.assertEqual(result["commonPoints"], [])
        self.assertEqual(result["uniqueMentions"], [])

    def test_hallucinated_quote_is_not_accepted(self):
        raw = {"uniqueMentions": [finding("영상에서 99% 할인합니다.",
                     (20, "99% 할인하는 중입니다."))]}
        self.assertEqual(self.ground(raw)["uniqueMentions"], [])

    def test_strong_common_requires_two_distinct_supported_videos(self):
        raw = {"commonPoints": [finding("클리오 쿠션이 언급됩니다.",
                  (20, "클리오 쿠션 솔직 리뷰"), (23, "클리오 메쉬 블러 쿠션"))]}
        result = self.ground(raw)
        self.assertEqual(len(result["commonPoints"]), 1)
        self.assertEqual({e["contentId"] for e in result["commonPoints"][0]["evidences"]}, {20, 23})
        self.assertTrue(all(e["timestampSeconds"] is None
                            for e in result["commonPoints"][0]["evidences"]))

    def test_one_valid_source_not_enough_when_other_audit_fails(self):
        raw = {"commonPoints": [finding("클리오 쿠션이 언급됩니다.",
                  (20, "클리오 쿠션 솔직 리뷰"), (23, "클리오 메쉬 블러 쿠션"))]}
        result = self.ground(raw, auditor=lambda checks: {checks[0]["key"]: True})
        self.assertEqual(len(result["commonPoints"]), 0)
        self.assertEqual(len(result["uniqueMentions"]), 1)

    def test_unique_video_quote_is_not_stated_as_verified_price(self):
        raw = {"uniqueMentions": [finding("제품의 공식 가격은 36,000원입니다.",
                    (21, "KRW 36000"))]}
        result = self.ground(raw)
        self.assertEqual(len(result["uniqueMentions"]), 1)
        statement = result["uniqueMentions"][0]["statement"]
        self.assertIn("KRW 36000", statement)
        self.assertNotIn("공식 가격", statement)

    def test_audit_unavailable_fails_closed(self):
        raw = {"commonPoints": [finding("클리오 쿠션이 언급됩니다.",
                  (20, "클리오 쿠션 솔직 리뷰"), (23, "클리오 메쉬 블러 쿠션"))]}
        result = self.ground(raw, auditor=lambda _: (_ for _ in ()).throw(RuntimeError("503")))
        self.assertEqual(result["commonPoints"], [])

    def test_disagreement_is_a_joint_relation(self):
        contexts = [
            {"contentId": 30, "summary": "지속력이 좋았어요."},
            {"contentId": 31, "summary": "지속력이 좋지 않았어요."},
        ]
        raw = {"disagreements": [finding("두 영상의 지속력 평가가 엇갈립니다.",
                      (30, "지속력이 좋았어요."), (31, "지속력이 좋지 않았어요."))]}
        def auditor(checks):
            self.assertEqual(len(checks), 1)
            self.assertIn("영상 30", checks[0]["quote"])
            self.assertIn("영상 31", checks[0]["quote"])
            return {checks[0]["key"]: True}
        result = ground_comparison_results(raw, contexts, semantic_audit=auditor)
        self.assertEqual(len(result["disagreements"]), 1)

    def test_numeric_format_variation_is_not_a_conflict(self):
        contexts = [
            {"contentId": 30, "summary": "정가 36000원"},
            {"contentId": 31, "summary": "정가 36,000원"},
        ]
        obj = {"field": "PRICE", "label": "가격", "values": ["36000원", "36,000원"],
               "evidences": [evidence(30, "정가 36000원"), evidence(31, "정가 36,000원")]}
        result = ground_comparison_results({"objectiveDisagreements": [obj]}, contexts)
        self.assertEqual(result["objectiveDisagreements"], [])

    def test_objective_disagreement_needs_distinct_explicit_values(self):
        contexts = [
            {"contentId": 30, "summary": "가격 36000원"},
            {"contentId": 31, "summary": "가격 38000원"},
        ]
        obj = {"field": "PRICE", "label": "가격", "values": ["36000원", "38000원"],
               "evidences": [evidence(30, "가격 36000원"), evidence(31, "가격 38000원")]}
        result = ground_comparison_results({"objectiveDisagreements": [obj]}, contexts)
        self.assertEqual(len(result["objectiveDisagreements"]), 1)
        obj["evidences"][1]["quote"] = "전컬러 발색 리뷰"
        result = ground_comparison_results({"objectiveDisagreements": [obj]}, contexts)
        self.assertEqual(result["objectiveDisagreements"], [])


if __name__ == "__main__":
    unittest.main()
