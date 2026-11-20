import unittest
from services.conflict_grounding import filter_detected_conflicts


def claim(cid, subject, amount, text=None):
    return {"contentId": cid, "subject": subject, "claimType": "PRICE",
            "claimText": text or f"{subject} 가격 {amount}원"}


def conflict(a, b, subject="다이소"):
    return {"subject": subject, "claimType": "PRICE", "title": "가격이 달라요",
            "description": "같은 대상의 가격이 다릅니다", "severity": "WARN",
            "evidences": [{"contentId": x["contentId"], "claimText": x["claimText"],
                           "value": ""} for x in (a, b)]}


class PriceConflictGroundingTests(unittest.TestCase):
    def test_daiso_brand_only_is_not_product_identity(self):
        a=claim(1,"다이소", "5,000", "다이소 스텐 수납바구니 가격 5,000원")
        b=claim(2,"다이소", "3,000", "다이소 립밤 화장품 가격 3,000원")
        self.assertEqual(filter_detected_conflicts([conflict(a,b)], [a,b]), [])

    def test_same_explicit_product_with_different_prices_is_kept(self):
        a=claim(1,"클리오 킬커버 메쉬 블러 쿠션", "36,000")
        b=claim(2,"클리오 킬커버 메쉬 블러 쿠션", "38,000")
        self.assertEqual(len(filter_detected_conflicts([conflict(a,b)], [a,b])),1)

    def test_bare_numbers_from_views_not_prices(self):
        a=claim(1,"클리오 킬커버 메쉬 블러 쿠션", "36,000")
        b=claim(2,"클리오 킬커버 메쉬 블러 쿠션", "1,059,439", "조회수 1,059,439회")
        self.assertEqual(filter_detected_conflicts([conflict(a,b)], [a,b]), [])

    def test_currency_format_variation_not_conflict(self):
        a=claim(1,"클리오 킬커버 메쉬 블러 쿠션", "36,000")
        b=claim(2,"클리오 킬커버 메쉬 블러 쿠션", "36000")
        self.assertEqual(filter_detected_conflicts([conflict(a,b)], [a,b]), [])

    def test_model_invented_evidence_not_accepted(self):
        a=claim(1,"클리오 킬커버 메쉬 블러 쿠션", "36,000")
        b=claim(2,"클리오 킬커버 메쉬 블러 쿠션", "38,000")
        fake=conflict(a,b)
        fake['evidences'][1]['claimText']='공식 가격 20000원'
        self.assertEqual(filter_detected_conflicts([fake], [a,b]), [])

    def test_duplicate_warning_collapsed(self):
        a=claim(1,"클리오 킬커버 메쉬 블러 쿠션", "36,000")
        b=claim(2,"클리오 킬커버 메쉬 블러 쿠션", "38,000")
        original=conflict(a,b)
        self.assertEqual(len(filter_detected_conflicts([original,dict(original)], [a,b])),1)

    def test_non_price_conflicts_unchanged(self):
        a={"contentId":1,"claimType":"OPENING_HOURS","subject":"카페 A","claimText":"카페 A는 9시에 열어요."}
        b={"contentId":2,"claimType":"OPENING_HOURS","subject":"카페 A","claimText":"카페 A는 10시에 열어요."}
        alert={"claimType":"OPENING_HOURS","title":"영업시간이 달라요", "evidences":[{"contentId":1,"claimText":a["claimText"]},{"contentId":2,"claimText":b["claimText"]}]}
        self.assertEqual(filter_detected_conflicts([alert], [a,b]), [alert])

    def test_no_product_identity_remains_unknown(self):
        a=claim(1,"다이소", "5,000", "다이소의 가격은 5000원")
        b=claim(2,"다이소", "3,000", "다이소의 가격은 3000원")
        self.assertEqual(filter_detected_conflicts([conflict(a,b)], [a,b]), [])

if __name__ == '__main__': unittest.main()
