from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from services.instagram_source import download_instagram_reel


def _fake_yt_dlp(calls: list[dict], formats: list[dict]):
    class FakeDownloadError(Exception):
        pass

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            calls.append(options)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def _path(self, info):
            return self.options["outtmpl"].replace("%(id)s", info["id"]).replace("%(ext)s", "mp4")

        def extract_info(self, url, download):
            info = {"id": "reel123", "title": "세로 릴스", "duration": 20, "formats": formats}
            if download:
                output = Path(self._path(info))
                output.write_bytes(b"fake-media" * 100)
                info["requested_downloads"] = [{"filepath": str(output)}]
            return info

        def prepare_filename(self, info):
            return self._path(info)

    package = types.ModuleType("yt_dlp")
    package.YoutubeDL = FakeYoutubeDL
    utils = types.ModuleType("yt_dlp.utils")
    utils.DownloadError = FakeDownloadError
    return {"yt_dlp": package, "yt_dlp.utils": utils}


class InstagramFormatSelectionTests(unittest.TestCase):
    """Vertical Reels: the 720p stream is 720x1280, so formats must not be filtered by height<=720."""

    def _download(self, formats):
        calls: list[dict] = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(sys.modules, _fake_yt_dlp(calls, formats)):
            download_instagram_reel("https://www.instagram.com/reel/reel123/", Path(temp_dir))
        return [c for c in calls if "format" in c]

    def test_video_only_streams_prefer_720p_by_shorter_side(self):
        downloads = self._download([
            {"vcodec": "vp09", "acodec": "none", "width": 720, "height": 1280},
            {"vcodec": "none", "acodec": "mp4a", "ext": "m4a"},
        ])
        video, audio = downloads
        self.assertEqual(video["format_sort"], ["res:720"])
        self.assertNotIn("height<=", video["format"])
        self.assertNotIn("format_sort", audio)

    def test_combined_stream_uses_same_sort(self):
        (media,) = self._download([
            {"vcodec": "avc1", "acodec": "mp4a", "width": 720, "height": 1280},
        ])
        self.assertEqual(media["format_sort"], ["res:720"])
        self.assertNotIn("height<=", media["format"])


if __name__ == "__main__":
    unittest.main()
