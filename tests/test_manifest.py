import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import sha256
from create_manifest import EXPECTED, create


class ManifestTests(unittest.TestCase):
    def test_manifest_requires_all_platforms_and_hashes_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for system, arch in EXPECTED:
                name = f"bungeemind-voice-{system}-{arch}-v1.2.3.tar.gz"
                archive = directory / name
                archive.write_bytes(f"{system}/{arch}".encode())
                item = {
                    "os": system,
                    "arch": arch,
                    "version": "v1.2.3",
                    "name": name,
                    "size": archive.stat().st_size,
                    "sha256": sha256(archive),
                    "whisper_cli": f"{system}-{arch}/bin/whisper-cli",
                    "ffmpeg": f"{system}-{arch}/bin/ffmpeg",
                }
                (directory / (name + ".metadata.json")).write_text(json.dumps(item), encoding="utf-8")
            manifest = create(directory, "v1.2.3")
            self.assertEqual(len(manifest["artifacts"]), 6)
            self.assertEqual({(item["os"], item["arch"]) for item in manifest["artifacts"]}, EXPECTED)
            self.assertIn("whisper_cpp_version", manifest)
            self.assertIn("ffmpeg_version", manifest)

    def test_manifest_rejects_prerelease_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "tag estable"):
                create(Path(temporary), "v1.2.3-rc.1")


if __name__ == "__main__":
    unittest.main()
