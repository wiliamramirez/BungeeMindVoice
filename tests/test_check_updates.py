import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_updates import latest_ffmpeg, latest_whisper, updates, version_key


PINS = {"whisper_cpp": {"version": "v1.9.4"}, "ffmpeg": {"version": "9.0.2"}}


class CheckUpdatesTest(unittest.TestCase):
    def test_ffmpeg_listing_uses_numeric_order(self):
        listing = 'href="ffmpeg-9.0.tar.xz" href="ffmpeg-9.0.2.tar.xz" href="ffmpeg-8.1.10.tar.xz" href="ffmpeg-snapshot.tar.bz2"'
        self.assertEqual(latest_ffmpeg(listing), "9.0.2")

    def test_ffmpeg_listing_without_tarballs_fails(self):
        with self.assertRaises(ValueError):
            latest_ffmpeg("<html></html>")

    def test_whisper_tag_must_be_stable(self):
        self.assertEqual(latest_whisper({"tag_name": "v1.10.0"}), "v1.10.0")
        with self.assertRaises(ValueError):
            latest_whisper({"tag_name": "nightly"})

    def test_version_key_pads_missing_patch(self):
        self.assertEqual(version_key("9.0"), (9, 0, 0))
        self.assertLess(version_key("v1.9.4"), version_key("v1.10.0"))

    def test_no_updates_when_pins_are_current(self):
        self.assertEqual(updates(PINS, "v1.9.4", "9.0.2"), [])

    def test_reports_each_newer_version(self):
        self.assertEqual(
            updates(PINS, "v1.10.0", "9.0.3"),
            [
                "Update available: whisper.cpp v1.10.0 (pinned v1.9.4)",
                "Update available: FFmpeg 9.0.3 (pinned 9.0.2)",
            ],
        )

    def test_older_upstream_is_not_an_update(self):
        self.assertEqual(updates(PINS, "v1.9.3", "9.0.1"), [])


if __name__ == "__main__":
    unittest.main()
