import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from common import PINS, ROOT, extract, fetch, run, sha256


TARGETS = {
    "macos-arm64": ("macos", "arm64"),
    "macos-x86_64": ("macos", "x86_64"),
    "windows-x86_64": ("windows", "x86_64"),
    "windows-arm64": ("windows", "arm64"),
    "linux-x86_64": ("linux", "x86_64"),
    "linux-arm64": ("linux", "arm64"),
}

FFMPEG_SELECT = re.compile(
    rb'ffmpeg_select="aformat_filter anull_filter atrim_filter crop_filter\n'
    rb'\s+format_filter hflip_filter null_filter rotate_filter\n'
    rb'\s+transpose_filter trim_filter vflip_filter"'
)


def _patch_ffmpeg_cli(source: Path) -> None:
    configure = source / "configure"
    content = configure.read_bytes()
    patched, replacements = FFMPEG_SELECT.subn(b'ffmpeg_select="aformat_filter anull_filter aresample_filter"', content)
    if replacements != 1:
        raise RuntimeError("El pin de FFmpeg no contiene el bloque ffmpeg_select esperado")
    configure.write_bytes(patched)


def _verify_ffmpeg_config(config: Path) -> None:
    enabled = {
        match.group(1)
        for line in config.read_text(encoding="utf-8").splitlines()
        if (match := re.fullmatch(r"CONFIG_([A-Z0-9_]+)=yes", line))
    }
    expected = {
        "FILE_PROTOCOL", "OGG_DEMUXER", "MP3_DEMUXER", "MOV_DEMUXER", "FLAC_DEMUXER", "WAV_DEMUXER",
        "AAC_DECODER", "FLAC_DECODER", "MP3_DECODER", "OPUS_DECODER", "VORBIS_DECODER",
        "PCM_S16LE_ENCODER", "WAV_MUXER", "AFORMAT_FILTER", "ANULL_FILTER", "ARESAMPLE_FILTER",
        "AAC_PARSER", "FLAC_PARSER", "MPEGAUDIO_PARSER", "OPUS_PARSER", "VORBIS_PARSER",
    }
    actual = {name for name in enabled if name.endswith(("_PROTOCOL", "_DEMUXER", "_DECODER", "_ENCODER", "_MUXER", "_FILTER", "_PARSER"))}
    internal = {"FRAME_THREAD_ENCODER"}
    non_pcm = {name for name in actual if name not in internal and not (name.startswith("PCM_") and name.endswith("_DECODER"))}
    libraries = {"AVCODEC", "AVFILTER", "AVFORMAT", "AVUTIL", "SWRESAMPLE"}
    if non_pcm != expected:
        raise RuntimeError(f"Componentes FFmpeg inesperados: {sorted(non_pcm ^ expected)}")
    if not libraries.issubset(enabled) or "FFMPEG" not in enabled or {"AVDEVICE", "SWSCALE", "FFPLAY", "FFPROBE"} & enabled:
        raise RuntimeError("FFmpeg habilitó una herramienta o biblioteca no permitida")
    if not any(name.startswith("PCM_") and name.endswith("_DECODER") for name in actual):
        raise RuntimeError("Faltan los decoders PCM solicitados")


def host_matches(target: str) -> None:
    os_name, arch = TARGETS[target]
    actual_os = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system())
    actual_arch = platform.machine().lower()
    if actual_arch in {"amd64", "x64"}:
        actual_arch = "x86_64"
    if actual_arch in {"aarch64", "arm64"}:
        actual_arch = "arm64"
    if (actual_os, actual_arch) != (os_name, arch):
        raise RuntimeError(f"El target {target} requiere runner {os_name}/{arch}; este es {actual_os}/{actual_arch}")


def _whisper_options(target: str, build_dir: Path) -> list[str]:
    os_name, arch = TARGETS[target]
    options = [
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DWHISPER_BUILD_IS_DEV=OFF",
        "-DWHISPER_BUILD_TESTS=OFF",
        "-DWHISPER_BUILD_EXAMPLES=ON",
        "-DWHISPER_BUILD_SERVER=OFF",
        "-DWHISPER_CURL=OFF",
        "-DWHISPER_SDL2=OFF",
        "-DWHISPER_COREML=OFF",
        "-DWHISPER_OPENVINO=OFF",
        "-DGGML_BACKEND_DL=OFF",
        "-DGGML_OPENMP=OFF",
        "-DGGML_NATIVE=OFF",
        "-DGGML_CPU_ALL_VARIANTS=OFF",
        "-DGGML_BLAS=OFF",
        "-DGGML_CCACHE=OFF",
    ]
    if arch == "x86_64":
        options.extend((
            "-DGGML_SSE42=ON",
            "-DGGML_AVX=ON",
            "-DGGML_AVX2=ON",
            "-DGGML_BMI2=ON",
            "-DGGML_AVX512=OFF",
            "-DGGML_AVX_VNNI=OFF",
        ))
        if os_name != "windows":
            options.extend(("-DGGML_FMA=ON", "-DGGML_F16C=ON"))
    else:
        options.append("-DGGML_CPU_ARM_ARCH=armv8-a")
    if os_name == "macos":
        deployment = PINS["macos_deployment_targets"][arch]
        options.extend((
            f"-DCMAKE_OSX_ARCHITECTURES={arch}",
            f"-DCMAKE_OSX_DEPLOYMENT_TARGET={deployment}",
            "-DGGML_METAL=ON",
            "-DGGML_METAL_EMBED_LIBRARY=ON",
            "-DGGML_METAL_MACOSX_VERSION_MIN=" + deployment,
        ))
    else:
        options.extend(("-DGGML_METAL=OFF", "-DGGML_METAL_EMBED_LIBRARY=OFF"))
    if os_name == "windows":
        options.extend((
            "-G",
            "Ninja",
            "-DCMAKE_C_COMPILER=clang-cl",
            "-DCMAKE_CXX_COMPILER=clang-cl",
            "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
            "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded",
        ))
    elif os_name == "linux":
        options.append("-DCMAKE_EXE_LINKER_FLAGS=-static-libgcc -static-libstdc++")
    return options


def build_whisper(target: str, source: Path, work: Path, stage: Path) -> Path:
    build_dir = work / "whisper-build"
    shutil.rmtree(build_dir, ignore_errors=True)
    cmake = shutil.which("cmake")
    if not cmake:
        raise RuntimeError("Falta CMake")
    run([cmake, "-S", source, "-B", build_dir, *_whisper_options(target, build_dir)])
    build_args = [cmake, "--build", build_dir, "--target", "whisper-cli", "--config", "Release"]
    if platform.system() != "Windows":
        build_args.extend(("--parallel", str(max(2, os.cpu_count() or 2))))
    run(build_args)
    exe = "whisper-cli.exe" if platform.system() == "Windows" else "whisper-cli"
    candidates = [path for path in build_dir.rglob(exe) if path.is_file()]
    if len(candidates) != 1:
        raise RuntimeError(f"Se esperaba un whisper-cli y se encontraron {len(candidates)}")
    destination = stage / "bin" / exe
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidates[0], destination)
    return destination


def _ffmpeg_options(target: str, prefix: Path) -> list[str]:
    os_name, arch = TARGETS[target]
    prefix_value = _cygpath(prefix) if os_name == "windows" else str(prefix)
    options = [
        f"--prefix={prefix_value}",
        "--disable-everything",
        "--disable-autodetect",
        "--disable-network",
        "--enable-small",
        "--enable-static",
        "--disable-shared",
        "--disable-debug",
        "--disable-doc",
        "--disable-ffplay",
        "--disable-ffprobe",
        "--disable-avdevice",
        "--disable-swscale",
        "--enable-ffmpeg",
        "--enable-protocol=file",
        "--enable-demuxer=ogg,mp3,mov,flac,wav",
        "--enable-decoder=opus,vorbis,mp3,aac,flac,pcm_*",
        "--enable-parser=aac,flac,mpegaudio,opus,vorbis",
        "--enable-encoder=pcm_s16le",
        "--enable-muxer=wav",
        "--enable-filter=aresample",
        "--enable-swresample",
        "--disable-asm",
    ]
    if os_name == "macos":
        deployment = PINS["macos_deployment_targets"][arch]
        options.extend((f"--extra-cflags=-mmacosx-version-min={deployment}", f"--extra-ldflags=-mmacosx-version-min={deployment}"))
    elif os_name == "linux":
        baseline = "x86-64-v3" if arch == "x86_64" else "armv8-a"
        options.extend((f"--extra-cflags=-march={baseline}", "--extra-ldflags=-static-libgcc -static-libstdc++"))
    else:
        options.extend(("--toolchain=msvc", f"--arch={'x86_64' if arch == 'x86_64' else 'aarch64'}", "--target-os=win32", "--extra-cflags=-MT"))
    return options


def _cygpath(path: Path) -> str:
    result = subprocess.run(["cygpath", "-u", str(path)], check=True, text=True, capture_output=True)
    return result.stdout.strip()


def _windows_build_environment() -> tuple[str, str]:
    bash = os.environ.get("BMV_MSYS2_BASH")
    if not bash or not Path(bash).is_file():
        raise RuntimeError("No se encontro el bash de MSYS2; configura BMV_MSYS2_BASH con la ruta de setup-msys2")
    msvc_bin = os.environ.get("BMV_MSVC_BIN")
    if not msvc_bin or not (Path(msvc_bin) / "link.exe").is_file():
        raise RuntimeError("No se encontro link.exe de MSVC en BMV_MSVC_BIN")
    return bash, _cygpath(Path(msvc_bin))


def _msys_command(script: str, msvc_bin: str) -> str:
    return "export PATH=" + shlex.quote(msvc_bin) + ":$PATH; " + script


def build_ffmpeg(target: str, source: Path, work: Path, stage: Path) -> Path:
    prefix = work / "ffmpeg-install"
    shutil.rmtree(prefix, ignore_errors=True)
    _patch_ffmpeg_cli(source)
    options = _ffmpeg_options(target, prefix)
    if platform.system() == "Windows":
        bash, msvc_bin = _windows_build_environment()
        if not shutil.which("make"):
            raise RuntimeError("El build de FFmpeg en Windows requiere make de MSYS2")
        command = " && ".join((
            f"cd {shlex.quote(_cygpath(source))}",
            "which cl && which link && ./configure " + " ".join(shlex.quote(option) for option in options),
        ))
        run([bash, "-lc", _msys_command(command, msvc_bin)])
    else:
        run(["./configure", *options], cwd=source)
    _verify_ffmpeg_config(source / "ffbuild" / "config.mak")
    if platform.system() == "Windows":
        bash, msvc_bin = _windows_build_environment()
        command = " && ".join((
            f"cd {shlex.quote(_cygpath(source))}",
            "make -j2",
            "make install",
        ))
        run([bash, "-lc", _msys_command(command, msvc_bin)])
    else:
        run(["make", f"-j{max(2, os.cpu_count() or 2)}"], cwd=source)
        run(["make", "install"], cwd=source)
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    source_exe = prefix / "bin" / exe
    if not source_exe.is_file():
        raise RuntimeError(f"No se generó {source_exe}")
    destination = stage / "bin" / exe
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_exe, destination)
    return destination


def _license_files(whisper: Path, ffmpeg: Path, stage: Path, ffmpeg_options: list[str]) -> None:
    licenses = stage / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(whisper / "LICENSE", licenses / "whisper.cpp-MIT.txt")
    shutil.copy2(ffmpeg / "COPYING.LGPLv2.1", licenses / "FFmpeg-LGPL-2.1.txt")
    patch_file = ROOT / "patches" / "ffmpeg-cli-audio-only.patch"
    shutil.copy2(patch_file, licenses / patch_file.name)
    source = PINS["ffmpeg"]
    configure = shlex.join(["./configure", *ffmpeg_options])
    (licenses / "FFmpeg-build.txt").write_text(
        "FFmpeg " + source["version"] + " is distributed under LGPL-2.1-or-later.\n"
        + "Source: " + source["source_url"] + "\n"
        + "Source SHA-256: " + source["sha256"] + "\n"
        + "Applied configure patch: " + patch_file.name + "\n"
        + "Patch SHA-256: " + sha256(patch_file) + "\n"
        + "Exact configure command used for this platform:\n"
        + configure + "\n",
        encoding="utf-8",
    )


def _archive(stage: Path, target: str, version: str, output: Path) -> Path:
    os_name, arch = TARGETS[target]
    output.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if os_name == "windows" else ".tar.gz"
    name = f"bungeemind-voice-{os_name}-{arch}-{version}{suffix}"
    archive = output / name
    base = f"bungeemind-voice-{os_name}-{arch}"
    if suffix == ".zip":
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as result:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    result.write(path, (Path(base) / path.relative_to(stage)).as_posix())
    else:
        with tarfile.open(archive, "w:gz") as result:
            result.add(stage, arcname=base)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--version", default=os.environ.get("BMV_VERSION", "workflow"))
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    host_matches(args.target)
    if platform.system() == "Windows":
        _windows_build_environment()
        if not shutil.which("make") or not shutil.which("which"):
            raise RuntimeError("El build de Windows requiere make y diffutils de MSYS2 en PATH")
    work = ROOT / "build" / args.target
    cache = ROOT / "build" / "downloads"
    whisper_archive = fetch(PINS["whisper_cpp"], cache, "whisper-" + PINS["whisper_cpp"]["version"] + ".tar.gz")
    ffmpeg_archive = fetch(PINS["ffmpeg"], cache, "ffmpeg-" + PINS["ffmpeg"]["version"] + ".tar.xz")
    test_model = fetch(PINS["test_model"], cache, "ggml-tiny.bin")
    whisper_source = extract(whisper_archive, work / "source-whisper")
    ffmpeg_source = extract(ffmpeg_archive, work / "source-ffmpeg")
    stage = work / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    whisper_cli = build_whisper(args.target, whisper_source, work, stage)
    ffmpeg_cli = build_ffmpeg(args.target, ffmpeg_source, work, stage)
    from verify import dependencies
    dependencies([whisper_cli, ffmpeg_cli])
    options = _ffmpeg_options(args.target, work / "ffmpeg-install")
    _license_files(whisper_source, ffmpeg_source, stage, options)
    metadata = {
        "os": TARGETS[args.target][0],
        "arch": TARGETS[args.target][1],
        "version": args.version,
        "whisper_cli": "bin/whisper-cli.exe" if platform.system() == "Windows" else "bin/whisper-cli",
        "ffmpeg": "bin/ffmpeg.exe" if platform.system() == "Windows" else "bin/ffmpeg",
    }
    (stage / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    from smoke_test import smoke
    smoke(stage / metadata["ffmpeg"], stage / metadata["whisper_cli"], test_model)
    archive = _archive(stage, args.target, args.version, args.output)
    metadata["name"] = archive.name
    metadata["size"] = archive.stat().st_size
    metadata["sha256"] = sha256(archive)
    metadata["whisper_cli"] = "bungeemind-voice-" + TARGETS[args.target][0] + "-" + TARGETS[args.target][1] + "/" + metadata["whisper_cli"]
    metadata["ffmpeg"] = "bungeemind-voice-" + TARGETS[args.target][0] + "-" + TARGETS[args.target][1] + "/" + metadata["ffmpeg"]
    (args.output / (archive.name + ".metadata.json")).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Paquete listo: {archive} ({archive.stat().st_size} bytes, sha256 {metadata['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
