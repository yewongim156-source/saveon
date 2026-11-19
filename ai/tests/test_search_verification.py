import os
import unittest
from unittest.mock import patch

from services import search_verification as sv
from services.fact_verifier import verify_structured_claims


def snippet(title, url, text, provider="tavily"):
    return {"title": title, "url": url, "snippet": text, "provider": provider}


class SearchVerificationTests(unittest.TestCase):
    def test_only_configured_providers_are_used_and_routed_by_claim_type(self):
        with patch.dict(os.environ, {"SEARCH_PROVIDERS": "wikipedia,tavily,kakao", "TAVILY_API_KEY": "", "KAKAO_REST_API_KEY": ""}):
            self.assertEqual(sv.providers_for("LOCATION"), ["wikipedia"])
        with patch.dict(os.environ, {"SEARCH_PROVIDERS": "wikipedia,tavily,kakao", "TAVILY_API_KEY": "t", "KAKAO_REST_API_KEY": "k"}):
            self.assertEqual(sv.providers_for("LOCATION"), ["kakao", "tavily", "wikipedia"])
            self.assertEqual(sv.providers_for("PRICE"), ["tavily"])

    def test_without_any_provider_nothing_is_searched_or_judged(self):
        with patch.dict(os.environ, {"SEARCH_PROVIDERS": "tavily", "TAVILY_API_KEY": ""}), \
                patch.object(sv, "_judge") as judge:
            result = sv.verify_claim_by_search({"text": "가게는 성수동에 있다", "type": "LOCATION"})
        judge.assert_not_called()
        self.assertEqual(result["verdict"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["sources"], [])

    def test_kakao_place_result_is_parsed(self):
        body = {"documents": [{"place_name": "커피냅로스터스", "road_address_name": "서울 성동구 아차산로 1",
                               "phone": "02-000-0000", "category_name": "카페", "place_url": "http://place.map.kakao.com/1"}]}
        with patch.dict(os.environ, {"KAKAO_REST_API_KEY": "k"}), patch.object(sv, "_http_json", return_value=body) as http:
            found = sv._search_kakao("커피냅로스터스 성수")
        self.assertEqual(found[0]["title"], "커피냅로스터스")
        self.assertIn("서울 성동구 아차산로 1", found[0]["snippet"])
        self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "KakaoAK k")

    def test_verdict_must_cite_a_supplied_snippet(self):
        snippets = [snippet("A", "https://a.example", "성수동 카페")]
        claim = {"text": "성수동에 있다", "type": "OTHER", "searchQuery": "성수동 카페"}
        cases = [
            ({"verdict": "SUPPORTED", "confidence": 0.9, "explanation": "확인", "supportingSnippetIndexes": [5]}, "INSUFFICIENT_EVIDENCE", []),
            ({"verdict": "SUPPORTED", "confidence": 0.9, "explanation": "확인", "supportingSnippetIndexes": [0]}, "SUPPORTED", ["https://a.example"]),
            ({"verdict": "BOGUS", "confidence": 0.9, "explanation": "?", "supportingSnippetIndexes": [0]}, "INSUFFICIENT_EVIDENCE", ["https://a.example"]),
        ]
        for parsed, verdict, urls in cases:
            with patch.dict(os.environ, {"SEARCH_PROVIDERS": "tavily", "TAVILY_API_KEY": "t"}), \
                    patch.object(sv, "GEMINI_API_KEY", "g"), \
                    patch.object(sv, "search_snippets", return_value=snippets), \
                    patch.object(sv, "_judge", return_value=parsed):
                result = sv.verify_claim_by_search(claim)
            self.assertEqual(result["verdict"], verdict)
            self.assertEqual([source["url"] for source in result["sources"]], urls)
            self.assertEqual(result["engine"], "search")

    def test_judge_falls_back_to_second_model_and_reports_model_errors(self):
        snippets = [snippet("A", "https://a.example", "내용")]
        claim = {"text": "주장", "type": "OTHER", "searchQuery": "q"}
        ok = {"verdict": "SUPPORTED", "confidence": 0.8, "explanation": "확인", "supportingSnippetIndexes": [0]}
        env = {"SEARCH_PROVIDERS": "tavily", "TAVILY_API_KEY": "t", "GEMINI_MODEL": "main-model"}
        with patch.dict(os.environ, env), patch.object(sv, "GEMINI_API_KEY", "g"), patch.object(sv, "SEARCH_MODEL", "lite-model"), \
                patch.object(sv, "search_snippets", return_value=snippets):
            with patch.object(sv, "_judge", side_effect=[RuntimeError("503"), ok]) as judge:
                recovered = sv.verify_claim_by_search(claim)
            self.assertEqual([call.args[2] for call in judge.call_args_list], [None, "main-model"])
            self.assertEqual(recovered["verdict"], "SUPPORTED")
            with patch.object(sv, "_judge", side_effect=RuntimeError("503")):
                failed = sv.verify_claim_by_search(claim)
        self.assertEqual((failed["verdict"], failed["error"]), ("INSUFFICIENT_EVIDENCE", "JUDGE_UNAVAILABLE"))
        self.assertIn("판정 모델 오류", failed["explanation"])
        self.assertEqual(failed["sources"], [])

    def test_failing_provider_does_not_stop_others(self):
        good = [snippet("B", "https://b.example", "내용", "wikipedia")]
        providers = {"tavily": (lambda q: (_ for _ in ()).throw(RuntimeError("down")), None), "wikipedia": (lambda q: good, None)}
        with patch.dict(os.environ, {"SEARCH_PROVIDERS": "tavily,wikipedia", "TAVILY_API_KEY": "t"}), \
                patch.object(sv, "PROVIDERS", providers):
            found = sv.search_snippets("질의", "OTHER")
        self.assertEqual([item["url"] for item in found], ["https://b.example"])

    def test_fact_checker_uses_search_engine_only_when_selected(self):
        structured = {"claims": [{"text": "주장", "type": "OTHER", "verifiable": True, "searchQuery": "q"}]}
        fake = {"claim": "주장", "verdict": "SUPPORTED", "sources": [{"url": "https://a.example"}]}
        with patch("services.fact_verifier.FACT_CHECK_ENABLED", True), patch("services.fact_verifier.GEMINI_API_KEY", "g"), \
                patch("services.fact_verifier.FACT_CHECK_ENGINE", "search"), \
                patch("services.search_verification.verify_claim_by_search", return_value=fake) as search, \
                patch("services.fact_verifier._verify_claim") as grounding:
            checked = verify_structured_claims(dict(structured))
        search.assert_called_once()
        grounding.assert_not_called()
        self.assertEqual(checked["factChecks"], [fake])


if __name__ == "__main__":
    unittest.main()
