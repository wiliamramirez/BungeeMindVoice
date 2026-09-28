import re
import subprocess
import tempfile
import wave
from pathlib import Path

from common import PINS, ROOT, fetch


EXPECTED_KEYWORDS = ("hello", "speech", "recognition", "test")


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def smoke(ffmpeg: Path, whisper_cli: Path, model_path: Path | None = None) -> None:
    if model_path is None:
        model_path = ROOT / "build" / "downloads" / "ggml-tiny.bin"
    entry = PINS["test_model"]
    model_path = fetch(entry, model_path.parent, model_path.name)
    if model_path.stat().st_size != entry["size"]:
        raise RuntimeError("Tamaño incorrecto del modelo tiny")
    with tempfile.TemporaryDirectory(prefix="bmv-smoke-") as temporary:
        wav_path = Path(temporary) / "speech-test.wav"
        subprocess.run([str(ffmpeg), "-y", "-loglevel", "error", "-i", str(ROOT / "testdata/speech-test.ogg"), "-ar", "16000", "-ac", "1", str(wav_path)], check=True, timeout=60)
        with wave.open(str(wav_path), "rb") as audio:
            if audio.getframerate() != 16000 or audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                raise RuntimeError("FFmpeg no generó WAV PCM s16le, mono y 16 kHz")
        result = subprocess.run(
            [str(whisper_cli), "-m", str(model_path), "-f", str(wav_path), "-l", "en", "-nt", "-np"],
            text=True,
            errors="replace",
            capture_output=True,
            timeout=300,
        )
        output = result.stdout + "\n" + result.stderr
        if result.returncode:
            raise RuntimeError("whisper-cli falló:\n" + output[-3000:])
        normalized = _normalized(output)
        missing = [word for word in EXPECTED_KEYWORDS if word not in normalized.split()]
        if missing:
            raise RuntimeError(f"La transcripción no contiene {', '.join(missing)}:\n{output[-3000:]}")
        print("Transcripción tiny OK: " + normalized)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("ffmpeg", type=Path)
    parser.add_argument("whisper_cli", type=Path)
    parser.add_argument("--model", type=Path)
    args = parser.parse_args()
    smoke(args.ffmpeg, args.whisper_cli, args.model)
