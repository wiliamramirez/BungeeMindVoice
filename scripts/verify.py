import platform
import re
import shutil
import subprocess
import os
from pathlib import Path


WINDOWS_SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "cfgmgr32.dll", "combase.dll", "comdlg32.dll",
    "crypt32.dll", "cryptbase.dll", "cryptsp.dll", "gdi32.dll", "imm32.dll", "iphlpapi.dll", "kernel32.dll",
    "msvcrt.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll", "rpcrt4.dll", "sechost.dll", "setupapi.dll",
    "shell32.dll", "shlwapi.dll", "user32.dll", "userenv.dll", "version.dll", "winmm.dll", "winspool.drv",
    "ws2_32.dll", "ucrtbase.dll", "normaliz.dll", "dnsapi.dll", "comctl32.dll", "psapi.dll", "winhttp.dll",
}


def _command(argv):
    result = subprocess.run(argv, text=True, errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Falló {' '.join(argv)}: {result.stderr.strip()}")
    return result.stdout + result.stderr


def _windows_dependencies(binary: Path) -> list[str]:
    output = _command([shutil.which("dumpbin") or "dumpbin", "/nologo", "/dependents", str(binary)])
    return [match.group(1).lower() for line in output.splitlines() if (match := re.search(r"([A-Za-z0-9_.+-]+\.(?:dll|drv))\s*$", line, re.I))]


def _system_windows(name: str) -> bool:
    if name.startswith(("api-ms-win-", "ext-ms-win-")):
        return True
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return name in WINDOWS_SYSTEM_DLLS or (Path(system_root) / "System32" / name).is_file()


def _mac_dependencies(binary: Path) -> list[str]:
    output = _command(["otool", "-L", str(binary)])
    dependencies = []
    for line in output.splitlines()[1:]:
        path = line.strip().split(" (", 1)[0]
        if path:
            dependencies.append(path)
    return dependencies


def _linux_dependencies(binary: Path) -> list[str]:
    output = _command(["ldd", str(binary)])
    dependencies = []
    for line in output.splitlines():
        if "not found" in line:
            dependencies.append(line.strip())
            continue
        match = re.search(r"=>\s+(/\S+)", line)
        if match:
            dependencies.append(match.group(1))
        elif line.strip().startswith("/"):
            dependencies.append(line.strip().split()[0])
    return dependencies


def dependencies(binaries: list[Path]) -> None:
    system = platform.system()
    for binary in binaries:
        if system == "Windows":
            linked = _windows_dependencies(binary)
            bad = [name for name in linked if not _system_windows(name)]
            banned = [name for name in linked if re.search(r"(?:vcruntime|msvcp|libomp|libgcc|libstdc\+\+)", name, re.I)]
        elif system == "Darwin":
            linked = _mac_dependencies(binary)
            bad = [name for name in linked if not name.startswith(("/usr/lib/", "/System/Library/", "/Library/Apple/System/Library/"))]
            banned = []
        elif system == "Linux":
            linked = _linux_dependencies(binary)
            bad = [name for name in linked if name.startswith("/") and not name.startswith(("/lib/", "/lib64/", "/usr/lib/", "/usr/lib64/"))]
            bad.extend(name for name in linked if "not found" in name)
            banned = [name for name in linked if re.search(r"(?:libomp|libgcc_s|libstdc\+\+)", name, re.I)]
        else:
            raise RuntimeError(f"Sistema no soportado: {system}")
        if bad or banned:
            raise RuntimeError(f"Dependencias no permitidas en {binary.name}: {', '.join(sorted(set(bad + banned)))}")
        print(f"Dependencias del sistema solamente: {binary.name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("binaries", nargs="+", type=Path)
    arguments = parser.parse_args()
    dependencies(arguments.binaries)
