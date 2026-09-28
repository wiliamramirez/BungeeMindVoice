import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build


class BuildOptionsTests(unittest.TestCase):
    def test_windows_build_script_normalizes_arch_and_checks_sdk_libraries(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "build-windows.cmd").read_text(encoding="ascii")
        self.assertIn('if /I "%TARGET_ARCH%"=="ARM64" set "TARGET_ARCH=arm64"', script)
        self.assertIn('if /I "%HOST_ARCH%"=="ARM64" set "HOST_ARCH=arm64"', script)
        self.assertIn('if /I "%TARGET_ARCH%"=="amd64" set "TARGET_DIR=x64"', script)
        self.assertIn('if /I "%HOST_ARCH%"=="amd64" set "HOST_DIR=x64"', script)
        self.assertIn('Host%HOST_DIR%\\%TARGET_DIR%', script)
        self.assertIn('set "SDK_UM_DIR=%WindowsSdkDir%Lib\\%WindowsSDKVersion%um\\%TARGET_DIR%"', script)
        self.assertIn('if not exist "%SDK_UM_DIR%\\kernel32.lib"', script)
        self.assertIn("echo LIB=%LIB%", script)
        self.assertNotIn("findstr", script)

    def test_ffmpeg_patch_reduces_cli_filter_selection(self):
        original = (
            b'ffmpeg_select="aformat_filter anull_filter atrim_filter crop_filter\n'
            b'               format_filter hflip_filter null_filter rotate_filter\n'
            b'               transpose_filter trim_filter vflip_filter"'
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            configure = source / "configure"
            configure.write_bytes(original)
            build._patch_ffmpeg_cli(source)
            self.assertEqual(configure.read_bytes(), b'ffmpeg_select="aformat_filter anull_filter aresample_filter"')

    def test_ffmpeg_config_rejects_unrequested_components(self):
        lines = [
            "CONFIG_AVCODEC=yes", "CONFIG_AVFILTER=yes", "CONFIG_AVFORMAT=yes", "CONFIG_AVUTIL=yes",
            "CONFIG_SWRESAMPLE=yes", "CONFIG_FFMPEG=yes", "CONFIG_FILE_PROTOCOL=yes",
            "CONFIG_OGG_DEMUXER=yes", "CONFIG_MP3_DEMUXER=yes", "CONFIG_MOV_DEMUXER=yes",
            "CONFIG_FLAC_DEMUXER=yes", "CONFIG_WAV_DEMUXER=yes", "CONFIG_AAC_DECODER=yes",
            "CONFIG_FLAC_DECODER=yes", "CONFIG_MP3_DECODER=yes", "CONFIG_OPUS_DECODER=yes",
            "CONFIG_VORBIS_DECODER=yes", "CONFIG_PCM_S16LE_DECODER=yes", "CONFIG_PCM_F32LE_DECODER=yes",
            "CONFIG_PCM_S16LE_ENCODER=yes", "CONFIG_WAV_MUXER=yes", "CONFIG_AFORMAT_FILTER=yes",
            "CONFIG_ANULL_FILTER=yes", "CONFIG_ARESAMPLE_FILTER=yes",
            "CONFIG_AAC_PARSER=yes", "CONFIG_FLAC_PARSER=yes", "CONFIG_MPEGAUDIO_PARSER=yes",
            "CONFIG_OPUS_PARSER=yes", "CONFIG_VORBIS_PARSER=yes", "CONFIG_FRAME_THREAD_ENCODER=yes",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.mak"
            config.write_text("\n".join(lines) + "\n", encoding="utf-8")
            build._verify_ffmpeg_config(config)
            config.write_text("\n".join(lines + ["CONFIG_CROP_FILTER=yes"]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Componentes FFmpeg inesperados"):
                build._verify_ffmpeg_config(config)

    def test_x86_linux_instruction_baseline_is_explicit(self):
        options = build._whisper_options("linux-x86_64", Path("build"))
        for option in ("-DGGML_AVX2=ON", "-DGGML_FMA=ON", "-DGGML_F16C=ON", "-DGGML_BMI2=ON"):
            self.assertIn(option, options)
        self.assertIn("-DGGML_CPU_ALL_VARIANTS=OFF", options)
        self.assertIn("-DGGML_BACKEND_DL=OFF", options)

    def test_arm_baseline_is_not_runner_native(self):
        for target in ("macos-arm64", "linux-arm64", "windows-arm64"):
            options = build._whisper_options(target, Path("build"))
            self.assertIn("-DGGML_NATIVE=OFF", options)
            self.assertIn("-DGGML_CPU_ARM_ARCH=armv8-a", options)

    def test_linux_cxx_runtimes_are_statically_linked(self):
        whisper = build._whisper_options("linux-x86_64", Path("build"))
        ffmpeg = build._ffmpeg_options("linux-x86_64", Path("/tmp/prefix"))
        self.assertIn("-DCMAKE_EXE_LINKER_FLAGS=-static-libgcc -static-libstdc++", whisper)
        self.assertIn("--extra-ldflags=-static-libgcc -static-libstdc++", ffmpeg)

    def test_macos_deployment_and_embedded_metal_are_explicit(self):
        options = build._whisper_options("macos-arm64", Path("build"))
        self.assertIn("-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0", options)
        self.assertIn("-DGGML_METAL=ON", options)
        self.assertIn("-DGGML_METAL_EMBED_LIBRARY=ON", options)

    def test_macos_intel_builds_without_metal(self):
        options = build._whisper_options("macos-x86_64", Path("build"))
        self.assertIn("-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0", options)
        self.assertIn("-DGGML_METAL=OFF", options)
        self.assertNotIn("-DGGML_METAL=ON", options)

    def test_ffmpeg_is_restricted_to_audio_and_file_io(self):
        options = build._ffmpeg_options("linux-arm64", Path("/tmp/prefix"))
        for option in (
            "--disable-everything",
            "--disable-network",
            "--enable-protocol=file",
            "--enable-demuxer=ogg,mp3,mov,flac,wav",
            "--enable-decoder=opus,vorbis,mp3,aac,flac,pcm_*",
            "--enable-encoder=pcm_s16le",
            "--enable-muxer=wav",
            "--enable-filter=aresample",
            "--enable-swresample",
            "--disable-avdevice",
            "--disable-swscale",
        ):
            self.assertIn(option, options)
        self.assertFalse(any("gpl" in option.lower() or "nonfree" in option.lower() for option in options))

    def test_windows_uses_static_msvc_runtime(self):
        with patch.object(build, "_cygpath", return_value="/tmp/prefix"):
            options = build._ffmpeg_options("windows-arm64", Path("C:/prefix"))
        self.assertIn("--toolchain=msvc", options)
        self.assertIn("--arch=aarch64", options)
        whisper = build._whisper_options("windows-arm64", Path("build"))
        self.assertIn("-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded", whisper)
        self.assertIn("-G", whisper)
        self.assertIn("Ninja", whisper)
        self.assertIn("-DCMAKE_C_COMPILER=clang-cl", whisper)
        self.assertIn("-DCMAKE_CXX_COMPILER=clang-cl", whisper)

    def test_msys_command_prioritizes_msvc_before_msys_link(self):
        command = build._msys_command("which cl && which link && ./configure", "/c/msvc/bin")
        self.assertTrue(command.startswith("export PATH=/c/msvc/bin:$PATH; "))
        self.assertIn("which cl && which link && ./configure", command)

    def test_ffmpeg_tools_are_checked_inside_msys2(self):
        with patch.object(build, "_cygpath", return_value="/c/source"):
            command = build._ffmpeg_configure_command(Path("C:/source"), ["--enable-static"])
        self.assertIn("command -v make && command -v cmp", command)
        self.assertIn("which cl && which link && ./configure --enable-static", command)

    def test_windows_build_requires_explicit_msys2_bash(self):
        with patch.dict(build.os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BMV_MSYS2_BASH"):
                build._windows_build_environment()

    def test_windows_x86_instruction_baseline_is_explicit(self):
        options = build._whisper_options("windows-x86_64", Path("build"))
        for option in ("-DGGML_AVX2=ON", "-DGGML_BMI2=ON"):
            self.assertIn(option, options)
        self.assertIn("-DGGML_CPU_ALL_VARIANTS=OFF", options)
        self.assertIn("-DGGML_BACKEND_DL=OFF", options)


if __name__ == "__main__":
    unittest.main()
