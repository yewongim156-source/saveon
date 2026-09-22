import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from services.youtube_source import (
    InvalidYouTubeUrlError,
    YouTubeSourceError,
    _positive_int_from_env,
    _validate_metadata,
    download_youtube_video,
    is_youtube_url,
)


class YouTubeUrlTests(unittest.TestCase):
    def test_accepts_watch_shorts_and_short_urls(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtube.com/shorts/abc123",
            "https://m.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
        ]

        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(is_youtube_url(url))

    def test_rejects_lookalike_hosts_and_credentials(self):
        invalid_urls = [
            "https://youtube.com.example.org/watch?v=abc123",
            "https://example.org/?next=youtube.com",
            "https://user:pass@youtube.com/watch?v=abc123",
            "ftp://youtube.com/watch?v=abc123",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(is_youtube_url(url))


class YouTubeMetadataTests(unittest.TestCase):
    def test_rejects_playlist_and_live_video(self):
        with self.assertRaises(InvalidYouTubeUrlError):
            _validate_metadata({"_type": "playlist"})

        with self.assertRaises(InvalidYouTubeUrlError):
            _validate_metadata({"is_live": True})

    def test_rejects_video_over_configured_duration(self):
        with patch.dict(
            os.environ,
            {"YOUTUBE_MAX_DURATION_SECONDS": "60"},
        ):
            with self.assertRaises(InvalidYouTubeUrlError):
                _validate_metadata({"duration": 61})

            _validate_metadata({"duration": 60})

    def test_positive_integer_environment_setting(self):
        with patch.dict(os.environ, {"SAVEON_TEST_LIMIT": "25"}):
            self.assertEqual(
                _positive_int_from_env("SAVEON_TEST_LIMIT", 10),
                25,
            )

        with patch.dict(os.environ, {"SAVEON_TEST_LIMIT": "invalid"}):
            with self.assertRaises(YouTubeSourceError):
                _positive_int_from_env("SAVEON_TEST_LIMIT", 10)


class YouTubeDownloadTests(unittest.TestCase):
    def test_download_returns_metadata_and_media_path(self):
        class FakeDownloadError(Exception):
            pass

        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def extract_info(self, url, download):
                info = {
                    "id": "short123",
                    "title": "테스트 쇼츠",
                    "description": "서울 카페를 소개합니다.",
                    "channel": "SaveOn Test",
                    "duration": 25,
                    "webpage_url": url,
                }
                if download:
                    output = Path(
                        self.options["outtmpl"].replace(
                            "%(id)s",
                            info["id"],
                        ).replace("%(ext)s", "mp4")
                    )
                    output.write_bytes(b"fake-video")
                    info["requested_downloads"] = [
                        {"filepath": str(output)}
                    ]
                return info

            def prepare_filename(self, info):
                return self.options["outtmpl"].replace(
                    "%(id)s",
                    info["id"],
                ).replace("%(ext)s", "mp4")

        fake_package = types.ModuleType("yt_dlp")
        fake_package.YoutubeDL = FakeYoutubeDL
        fake_utils = types.ModuleType("yt_dlp.utils")
        fake_utils.DownloadError = FakeDownloadError

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            sys.modules,
            {"yt_dlp": fake_package, "yt_dlp.utils": fake_utils},
        ):
            media = download_youtube_video(
                "https://youtube.com/shorts/short123",
                Path(temp_dir),
            )

            self.assertTrue(media.path.is_file())
            self.assertEqual(media.audio_path, media.path)
            self.assertEqual(media.video_id, "short123")
            self.assertEqual(media.title, "테스트 쇼츠")
            self.assertEqual(media.channel, "SaveOn Test")
            self.assertEqual(media.duration_seconds, 25)


if __name__ == "__main__":
    unittest.main()
