import json
import os
import re
import urllib.request

from common import PINS


WHISPER_LATEST_URL = "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest"
FFMPEG_RELEASES_URL = "https://ffmpeg.org/releases/"
FFMPEG_TARBALL = re.compile(r"ffmpeg-(\d+\.\d+(?:\.\d+)?)\.tar\.xz")


def version_key(version: str) -> tuple[int, int, int]:
    parts = [int(part) for part in version.lstrip("v").split(".")]
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"Versión no reconocida: {version}")
    return tuple(parts + [0] * (3 - len(parts)))


def latest_ffmpeg(listing: str) -> str:
    versions = set(FFMPEG_TARBALL.findall(listing))
    if not versions:
        raise ValueError("No se encontraron tarballs de FFmpeg en el listado")
    return max(versions, key=version_key)


def latest_whisper(release: dict) -> str:
    tag = release.get("tag_name", "")
    if not re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", tag):
        raise ValueError(f"Tag de whisper.cpp no reconocido: {tag!r}")
    return tag


def updates(pins: dict, whisper: str, ffmpeg: str) -> list[str]:
    found = []
    for name, latest, pinned in (
        ("whisper.cpp", whisper, pins["whisper_cpp"]["version"]),
        ("FFmpeg", ffmpeg, pins["ffmpeg"]["version"]),
    ):
        if version_key(latest) > version_key(pinned):
            found.append(f"Update available: {name} {latest} (pinned {pinned})")
    return found


def _fetch(url: str) -> str:
    headers = {"User-Agent": "BungeeMindVoice-update-check"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    whisper = latest_whisper(json.loads(_fetch(WHISPER_LATEST_URL)))
    ffmpeg = latest_ffmpeg(_fetch(FFMPEG_RELEASES_URL))
    for title in updates(PINS, whisper, ffmpeg):
        print(title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
