import argparse
import json
import re
from pathlib import Path

from common import PINS, sha256


EXPECTED = {
    ("macos", "arm64"),
    ("macos", "x86_64"),
    ("windows", "arm64"),
    ("windows", "x86_64"),
    ("linux", "arm64"),
    ("linux", "x86_64"),
}


def create(directory: Path, version: str) -> dict:
    if not re.fullmatch(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("La versión del release debe ser un tag estable vX.Y.Z")
    artifacts = []
    for metadata_path in sorted(directory.glob("*.metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("version") != version:
            raise ValueError(f"Versión incorrecta en {metadata_path.name}")
        archive = directory / metadata["name"]
        if not archive.is_file():
            raise ValueError(f"Falta el paquete {metadata['name']}")
        if archive.stat().st_size != metadata["size"] or sha256(archive) != metadata["sha256"]:
            raise ValueError(f"Tamaño o SHA-256 incorrecto para {archive.name}")
        artifacts.append({
            "os": metadata["os"],
            "arch": metadata["arch"],
            "filename": archive.name,
            "size": metadata["size"],
            "sha256": metadata["sha256"],
            "whisper_cli": metadata["whisper_cli"],
            "ffmpeg": metadata["ffmpeg"],
        })
    actual = {(item["os"], item["arch"]) for item in artifacts}
    if actual != EXPECTED or len(artifacts) != len(EXPECTED):
        raise ValueError(f"Se esperaban exactamente seis plataformas; recibidas: {sorted(actual)}")
    return {
        "version": version,
        "whisper_cpp_version": PINS["whisper_cpp"]["version"],
        "ffmpeg_version": PINS["ffmpeg"]["version"],
        "artifacts": sorted(artifacts, key=lambda item: (item["os"], item["arch"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("dist"))
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    manifest = create(args.directory, args.version)
    destination = args.directory / "manifest.json"
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest listo: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
