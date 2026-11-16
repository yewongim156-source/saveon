"""Regression tests: no hallucinated outcomes, preserve provenance and counts."""
import unittest

from services.video_observations import extract_video_observations, review_excerpt_lines


class VideoObservationsV8Tests(unittest.TestCase):
    def test_title_mentions_eight_hour_test_without_claiming_result(self):
        data = extract_video_observations(source_title="클리오 쿠션 8시간 지속력 다크닝 검증")
        self.assertTrue(data)
        self.assertTrue(all(item['kind'] == 'TOPIC_MENTION' for item in data))
        self.assertFalse(any('좋다' in item['quote'] for item in data))

    def test_spoken_result_keeps_verbatim_source(self):
        phrase = "8시간 후에도 다크닝이 없었어요."
        data = extract_video_observations(transcript=phrase)
        self.assertTrue(any(x['kind'] == 'DIRECT_STATEMENT' for x in data))
        self.assertTrue(all(x['source'] == 'STT' for x in data))
        self.assertTrue(all(x['quote'] in phrase for x in data))

    def test_title_claim_not_mislabeled_spoken_result(self):
        data = extract_video_observations(source_title="다크닝 없는 쿠션 출시")
        self.assertTrue(data)
        self.assertEqual(data[0]['kind'], 'TOPIC_MENTION')
        self.assertEqual(data[0]['source'], 'TITLE')

    def test_test_mention_is_not_result(self):
        data = extract_video_observations(transcript="이 쿠션의 지속력 테스트를 해볼게요.")
        self.assertTrue(data)
        self.assertTrue(all(x['kind'] == 'TOPIC_MENTION' for x in data))

    def test_question_is_not_factual_outcome(self):
        data = extract_video_observations(transcript="8시간 뒤에도 다크닝이 없었어요?")
        self.assertTrue(data)
        self.assertTrue(all(x['kind'] == 'TOPIC_MENTION' for x in data))

    def test_ocr_is_unverified_even_when_it_says_positive(self):
        data = extract_video_observations(ocr_lines=["모공을 완벽하게 커버해요"])
        self.assertTrue(data)
        self.assertTrue(all(x['kind'] == 'OCR_UNVERIFIED' for x in data))

    def test_ocr_noise_is_filtered(self):
        data = extract_video_observations(ocr_lines=["b##", "와!?", "1;"])
        self.assertEqual(data, [])

    def test_all_colours_never_becomes_five(self):
        data = extract_video_observations(source_title="클리오 전컬러 발색 리뷰")
        self.assertTrue(any(x['topic'] == '색상' for x in data))
        self.assertFalse(any('5가지' in x['quote'] for x in data))

    def test_original_quote_substring_is_preserved(self):
        transcript = "이 제품은요 " + "그래서 이렇게 설명합니다 " * 30 + "8시간 후에도 다크닝은 없었어요."
        data = extract_video_observations(transcript=transcript)
        self.assertTrue(any(x['topic'] == '다크닝' for x in data))
        self.assertTrue(all(x['quote'] in transcript for x in data))

    def test_priority_spoken_result_over_metadata(self):
        data = extract_video_observations(
            transcript="모공이 잘 커버돼요.",
            source_title="클리오 쿠션 모공 커버 리뷰",
        )
        self.assertEqual(data[0]['source'], 'STT')
        self.assertEqual(data[0]['kind'], 'DIRECT_STATEMENT')

    def test_evidence_digest_excludes_ocr_and_titles(self):
        data = extract_video_observations(
            transcript="지속력이 좋았어요.",
            source_title="지속력 테스트",
            ocr_lines=["다크닝이 좋았어요"],
        )
        snippets = review_excerpt_lines(data)
        self.assertTrue(snippets)
        self.assertTrue(all('[STT/' in x or '[DESCRIPTION/' in x for x in snippets))
        self.assertTrue(any('좋았어요' in x for x in snippets))

    def test_duplicate_quote_is_not_repeated(self):
        data = extract_video_observations(transcript="다크닝이 없었어요. 다크닝이 없었어요.")
        self.assertEqual(len([x for x in data if x['topic'] == '다크닝']), 1)

    def test_limits(self):
        t = "지속력 다크닝 모공 블러 발색 색상 퍼프 브러시 가격 " * 50
        data = extract_video_observations(transcript=t, max_items=7)
        self.assertLessEqual(len(data), 7)
        self.assertLessEqual(len(review_excerpt_lines(data, max_items=3)), 3)

    def test_missing_inputs(self):
        self.assertEqual(extract_video_observations(), [])
        self.assertEqual(review_excerpt_lines([]), [])

    def test_v7_fallback_uses_direct_stt_quote(self):
        from services.comparison_grounding import ground_comparison_results
        original = "8시간 후에도 다크닝이 없었어요."
        context = {
            "contentId": 21,
            "title": "8시간 지속력 테스트",
            "summary": "8시간 테스트를 다룹니다.",
            "videoObservations": extract_video_observations(transcript=original),
        }
        result = ground_comparison_results({}, [context], fallback_when_empty=True)
        self.assertEqual(len(result['uniqueMentions']), 1)
        item = result['uniqueMentions'][0]
        self.assertIn('원본 영상 검증 전', item['statement'])
        self.assertIn('다크닝이 없었어요', item['statement'])
        self.assertEqual(item['evidences'][0]['quote'], original)

    def test_v7_grounding_accepts_real_observation_quote(self):
        from services.comparison_grounding import ground_comparison_results
        quote = "다크닝은 없었어요."
        context = {
            'contentId': 21,
            'title': '지속력 테스트',
            'summary': '8시간 테스트 영상',
            'videoObservations': extract_video_observations(transcript=quote),
        }
        raw = {'uniqueMentions': [{
            'topic': '다크닝', 'statement': '영상에서 다크닝이 없었다고 언급합니다.',
            'evidences': [{'contentId': 21, 'quote': quote}],
        }]}
        result = ground_comparison_results(
            raw, [context],
            semantic_audit=lambda checks: {x['key']: True for x in checks},
        )
        self.assertEqual(len(result['uniqueMentions']), 1)
        self.assertEqual(result['uniqueMentions'][0]['evidences'][0]['quote'], quote)


if __name__ == '__main__':
    unittest.main()
