import hashlib
import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "pins.json").read_text(encoding="utf-8"))


def run(argv, *, cwd=None, env=None):
    import subprocess

    print("+", " ".join(str(part) for part in argv), flush=True)
    subprocess.run([str(part) for part in argv], cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(entry: dict, cache: Path, filename: str) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / filename
    if destination.is_file() and sha256(destination) == entry["sha256"]:
        return destination
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(entry["source_url"], headers={"User-Agent": "BungeeMindVoice-build"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        actual = sha256(temporary)
        if actual != entry["sha256"]:
            raise ValueError(f"SHA-256 incorrecto para {filename}: {actual}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def extract(archive: Path, destination: Path) -> Path:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:*") as source:
        members = source.getmembers()
        for member in members:
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Ruta fuera del archivo fuente: {member.name}")
            if member.issym() or member.islnk():
                link_target = (target.parent / member.linkname).resolve()
                if link_target != root and root not in link_target.parents:
                    raise ValueError(f"Enlace fuera del archivo fuente: {member.name}")
        source.extractall(destination, members=members)
    children = list(destination.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError(f"Se esperaba una carpeta raíz en {archive.name}")
    return children[0]
