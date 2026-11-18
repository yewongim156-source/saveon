import unittest
from unittest.mock import patch

from services.external_reference import add_educational_reference


class ExternalReferenceTests(unittest.TestCase):
    def test_educational_match_adds_attributed_background_not_verification(self):
        result = {"summary": "영상 요약", "structured": {"contentType": "EDUCATIONAL", "verificationStatus": "INSUFFICIENT_EVIDENCE", "targets": [{"name": "양자 컴퓨터", "nameEvidenceIds": ["ocr-1"]}]}}
        ref = {"source": "한국어 위키백과", "title": "양자 컴퓨터", "text": "백과사전 설명", "url": "https://ko.wikipedia.org/wiki/test", "status": "BACKGROUND_NOT_VERIFIED"}
        with patch("services.external_reference._lookup_exact_title", return_value=ref):
            output = add_educational_reference(result)
        self.assertIn("관련 참고", output["summary"])
        self.assertIn(ref["url"], output["summary"])
        self.assertEqual(output["structured"]["verificationStatus"], "INSUFFICIENT_EVIDENCE")

    def test_product_and_network_failure_never_add_reference(self):
        result = {"summary": "원본", "structured": {"contentType": "PRODUCT_REVIEW", "targets": [{"name": "제품", "nameEvidenceIds": ["x"]}]}}
        with patch("services.external_reference._lookup_exact_title") as lookup:
            self.assertEqual(add_educational_reference(result)["summary"], "원본")
            lookup.assert_not_called()
        result["structured"]["contentType"] = "EDUCATIONAL"
        with patch("services.external_reference._lookup_exact_title", side_effect=OSError("offline")):
            self.assertEqual(add_educational_reference(result)["summary"], "원본")
