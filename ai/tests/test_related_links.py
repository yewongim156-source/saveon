import unittest
from unittest.mock import patch

from services import related_links as rl


class RelatedLinksTest(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(rl.classify("https://blog.naver.com/abc/1"), "블로그")
        self.assertEqual(rl.classify("https://zigzag.kr/catalog/1"), "쇼핑")
        self.assertEqual(rl.classify("https://map.naver.com/p/1"), "장소")
        self.assertIsNone(rl.classify("https://www.youtube.com/watch?v=1"))

    def test_query_uses_title_and_new_keywords(self):
        query = rl.build_query("서울숲 데이트 코스 #shorts", ["서울숲", "성수 카페", "산책", "맛집"])
        self.assertEqual(query, "서울숲 데이트 코스 성수 카페 산책")

    def test_supported_sources_come_first_and_are_deduped(self):
        checks = [{"verdict": "SUPPORTED", "sources": [{"title": "상품", "url": "https://zigzag.kr/a"}]},
                  {"verdict": "CONFLICTING", "sources": [{"title": "x", "url": "https://zigzag.kr/b"}]}]
        found = [{"title": "후기", "url": "https://blog.naver.com/x/1"}, {"title": "상품", "url": "https://zigzag.kr/a"}]
        with patch.object(rl, "enabled", return_value=True), patch.object(rl.sv, "_search_tavily", return_value=found):
            links = rl.find_related_links("제목", [], checks)
        self.assertEqual([l["url"] for l in links], ["https://zigzag.kr/a", "https://blog.naver.com/x/1"])

    def test_search_failure_keeps_verified_links(self):
        checks = [{"verdict": "SUPPORTED", "sources": [{"title": "t", "url": "https://map.naver.com/p/1"}]}]
        with patch.object(rl, "enabled", return_value=True), patch.object(rl.sv, "_search_tavily", side_effect=RuntimeError):
            self.assertEqual(len(rl.find_related_links("제목", [], checks)), 1)


if __name__ == "__main__":
    unittest.main()
