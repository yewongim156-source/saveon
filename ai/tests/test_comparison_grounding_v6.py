import unittest

from services.comparison_grounding import ground_comparison_results


def item(cid, quote):
    return {"contentId": cid, "title": f"영상 {cid}", "quote": quote,
            "timestampSeconds": 123.0}


def finding(statement, *items):
    return {"topic": "제품 리뷰", "statement": statement,
            "evidences": [item(*x) for x in items]}


def allow_all(checks):
    return {x["key"]: True for x in checks}


class ComparisonV6Tests(unittest.TestCase):
    def setUp(self):
        self.contexts = [
            {"contentId": 20, "title": "클리오 킬커버 메쉬 블러 쿠션 솔직 리뷰",
             "summary": "모공을 깔끔하게 커버하기 위한 얇은 레이어링과 브러시 사용 팁을 소개합니다.",
             "keywords": ["클리오", "블러 쿠션", "베이스 메이크업"]},
            {"contentId": 21, "title": "클리오 킬커버 쿠션 전컬러 발색 리뷰",
             "summary": "8시간 지속력 테스트와 전컬러 발색 리뷰를 진행합니다. KRW 36000",
             "keywords": ["쿠션", "클리오", "킬커버"]},
            {"contentId": 23, "title": "클리오 메쉬 블러 쿠션 모공 블러링",
             "summary": "모공 사이사이 매끈하게 밀착되어 블러리한 피부 표현으로 만들어줘요. 다섯 가지 컬러로 출시됐어요.",
             "keywords": ["메쉬", "모공", "블러", "컬러"]},
        ]

    def test_clio_v5_1_empty_becomes_shared_topic_and_per_video_info(self):
        result = ground_comparison_results(
            {"comparisonEntity": "클리오", "commonPoints": [],
             "disagreements": [], "uniqueMentions": []},
            self.contexts, semantic_audit=allow_all, fallback_when_empty=True)
        self.assertGreaterEqual(len(result["commonPoints"]), 1)
        self.assertEqual({x["contentId"] for x in result["uniqueMentions"][0]["evidences"]}, {20})
        self.assertEqual(len(result["uniqueMentions"]), 3)
        for common in result["commonPoints"]:
            self.assertIn("평가 일치", common["topic"])
            self.assertNotIn("뛰어", common["statement"])
            self.assertGreaterEqual(len({e["contentId"] for e in common["evidences"]}), 2)
            for ev in common["evidences"]:
                source = next(x for x in self.contexts if x["contentId"] == ev["contentId"])
                self.assertTrue(ev["quote"] in source["summary"] or ev["quote"] in source["title"])
                self.assertIsNone(ev["timestampSeconds"])

    def test_overstated_quality_not_accepted_as_common(self):
        bad = finding("모공 커버력이 뛰어난 제품입니다.",
                      (20, "모공을 깔끔하게 커버하기 위한 얇은 레이어링과 브러시 사용 팁을 소개합니다."),
                      (23, "모공 사이사이 매끈하게 밀착되어 블러리한 피부 표현으로 만들어줘요."))
        result = ground_comparison_results(
            {"comparisonEntity": "클리오", "commonPoints": [bad]},
            self.contexts, semantic_audit=allow_all, fallback_when_empty=True)
        self.assertFalse(any("뛰어난 제품" in f["statement"] for f in result["commonPoints"]))

    def test_all_colors_does_not_prove_five_colors(self):
        bad = finding("총 5가지 컬러로 출시", (21, "전컬러 발색 리뷰"),
                      (23, "다섯 가지 컬러로 출시됐어요."))
        result = ground_comparison_results(
            {"comparisonEntity": "클리오", "commonPoints": [bad]},
            self.contexts, semantic_audit=allow_all, fallback_when_empty=True)
        self.assertFalse(any("5가지" in x["statement"] for x in result["commonPoints"]))

    def test_actual_shared_claim_still_survives(self):
        contexts = [
            {"contentId": 51, "summary": "수분감이 좋다는 평가입니다."},
            {"contentId": 52, "summary": "수분감이 좋아서 만족했어요."},
        ]
        raw = {"commonPoints": [finding("두 영상 모두 수분감이 좋다고 평가합니다.",
                         (51, "수분감이 좋다는 평가입니다."), (52, "수분감이 좋아서 만족했어요."))]}
        result = ground_comparison_results(raw, contexts, semantic_audit=allow_all,
                                           fallback_when_empty=True)
        self.assertEqual(len(result["commonPoints"]), 1)
        self.assertEqual(len(result["commonPoints"][0]["evidences"]), 2)

    def test_contradiction_survives_joint_audit(self):
        contexts = [
            {"contentId": 51, "summary": "지속력이 좋았습니다."},
            {"contentId": 52, "summary": "지속력이 좋지 않았습니다."},
        ]
        raw = {"disagreements": [finding("지속력에 대한 평가가 엇갈립니다.",
                            (51, "지속력이 좋았습니다."), (52, "지속력이 좋지 않았습니다."))]}
        result = ground_comparison_results(raw, contexts, semantic_audit=allow_all,
                                           fallback_when_empty=True)
        self.assertEqual(len(result["disagreements"]), 1)

    def test_no_hallucinated_quotes(self):
        raw = {"commonPoints": [finding("모공 효과가 좋다고 합니다.",
                        (20, "모공을 99% 완벽히 없앤다는 거짓 문장"),
                        (23, "모공을 99% 완벽히 없앤다는 거짓 문장"))]}
        result = ground_comparison_results(raw, self.contexts,
                                           semantic_audit=allow_all, fallback_when_empty=True)
        self.assertFalse(any("99%" in e["quote"] for f in result["commonPoints"]
                             for e in f["evidences"]))

    def test_paraphrase_relinked_to_literal_source_excerpt(self):
        contexts = [
            {"contentId": 50, "summary": "얇은 레이어링과 브러시 사용 팁을 알려줍니다."},
            {"contentId": 51, "summary": "얇은 레이어링과 브러시 사용 팁을 공유합니다."},
        ]
        raw = {"commonPoints": [finding("두 영상에서 얇은 레이어링과 브러시 사용 팁을 소개합니다.",
                  (50, "얇은 레이어링과 브러시 사용 팁을 소개합니다."),
                  (51, "얇은 레이어링과 브러시 사용 팁을 소개합니다."))]}
        result = ground_comparison_results(raw, contexts, semantic_audit=allow_all,
                                           fallback_when_empty=False)
        self.assertEqual(len(result["commonPoints"]), 1)
        for ev in result["commonPoints"][0]["evidences"]:
            self.assertIn(ev["quote"], next(x["summary"] for x in contexts if x["contentId"]==ev["contentId"]))

    def test_semantic_audit_failure_stays_explicitly_unverified(self):
        raw = {"commonPoints": [finding("모공 커버 효과가 확실합니다.",
                  (20, "모공을 깔끔하게 커버하기 위한 얇은 레이어링과 브러시 사용 팁을 소개합니다."),
                  (23, "모공 사이사이 매끈하게 밀착되어 블러리한 피부 표현으로 만들어줘요."))]}
        result = ground_comparison_results(raw, self.contexts,
                                           semantic_audit=lambda _: {}, fallback_when_empty=True)
        self.assertTrue(all("효과가 확실" not in x["statement"] for x in result["commonPoints"]))
        self.assertTrue(all("평가 일치" in x["topic"] for x in result["commonPoints"]))

    def test_empty_with_no_real_overlap_stays_per_video_only(self):
        contexts = [{"contentId": 30, "title": "사과 청소 방법", "summary": "사과를 씻는 팁입니다."},
                    {"contentId": 31, "title": "인공지능 논문 정리", "summary": "인공지능 학습 소개입니다."}]
        result = ground_comparison_results({}, contexts, fallback_when_empty=True)
        self.assertEqual(result["commonPoints"], [])
        self.assertEqual(len(result["uniqueMentions"]), 2)

    def test_arbitrary_product_brand_alone_not_a_shared_topic(self):
        contexts = [
            {"contentId": 60, "title": "나이키 신발 사이즈 리뷰", "summary": "나이키 운동화 착용 후기", "keywords": ["나이키"]},
            {"contentId": 61, "title": "나이키 매장 방문", "summary": "나이키 매장 오픈 소식", "keywords": ["나이키"]},
        ]
        result = ground_comparison_results({}, contexts, comparison_entity="나이키", fallback_when_empty=True)
        self.assertEqual(result["commonPoints"], [])
        self.assertEqual(len(result["uniqueMentions"]), 2)

    def test_unrelated_brand_not_marked_shared(self):
        contexts = [{"contentId": 30, "title": "클리오 쿠션 리뷰", "summary": "클리오 쿠션 설명"},
                    {"contentId": 31, "title": "클리오 브랜드 소개", "summary": "클리오 브랜드 설명"}]
        result = ground_comparison_results({"comparisonEntity": "클리오"}, contexts,
                                           fallback_when_empty=True)
        self.assertEqual(result["commonPoints"], [])


if __name__ == "__main__":
    unittest.main()
