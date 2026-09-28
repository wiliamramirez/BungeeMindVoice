# BungeeMind Voice

Binarios portables de voz que BungeeMind descarga y verifica para transcribir audio localmente. Este repositorio contiene scripts de build y paquetes de software libre de terceros; no contiene código de BungeeMind.

## Plataformas

Cada Release publica un archivo por plataforma. Los nombres `os` y `arch` del manifest son estables: `macos`, `windows` o `linux`, y `arm64` o `x86_64`.

| OS | Arquitectura | Runner de Actions | Base mínima |
| --- | --- | --- | --- |
| macOS | arm64 | `macos-15` | macOS 12.0 |
| macOS | x86_64 | `macos-15-intel` | macOS 12.0 |
| Windows | x86_64 | `windows-2025` | Windows x64 |
| Windows | arm64 | `windows-11-arm` | Windows ARM64 |
| Linux | x86_64 | `ubuntu-22.04` | glibc 2.35 |
| Linux | arm64 | `ubuntu-22.04-arm` | glibc 2.35 |

Los paquetes x86_64 requieren una CPU x86-64-v3. whisper.cpp activa explícitamente SSE4.2, AVX, AVX2, BMI2, FMA y F16C; AVX2 implica FMA y F16C en el toolchain MSVC usado para Windows. Los binarios arm64 fijan ARMv8-A, sin extensiones del procesador del runner. En macOS, Metal está activado y su biblioteca queda embebida en `whisper-cli`.

El deployment target mínimo es macOS 12.0 en ambas arquitecturas. whisper.cpp 1.9.4 usa una API Metal disponible desde esa versión; el pin aplica el mismo mínimo a CMake y FFmpeg mediante `-mmacosx-version-min`.

## Contenido y versiones

Las versiones, URL y SHA-256 de los tarballs fuente están centralizados en [`pins.json`](pins.json). El build verifica cada hash antes de extraer o compilar. La primera versión planeada usa whisper.cpp v1.9.4 y FFmpeg 9.0.2.

Cada paquete contiene `whisper-cli`, `ffmpeg` y sus licencias. FFmpeg se configura como LGPL-2.1-or-later, estático, sin autodetección, sin red y con los componentes de audio para Ogg/Opus, Ogg/Vorbis, MP3, M4A/AAC, FLAC y WAV. El build aplica un parche LGPL pequeño al selector de filtros de la herramienta FFmpeg para registrar `aformat`, `anull` y `aresample`, los filtros de formato y reescalado de audio que usa la CLI; el parche y su hash van en el paquete. Convierte al formato WAV PCM de 16 bits, mono y 16 kHz que consume BungeeMind.

## Publicar

`workflow_dispatch` compila, ejecuta la prueba de transcripción en los seis runners y deja los paquetes como artefactos, sin crear un Release. Para publicar, crea y sube un tag estable `vX.Y.Z`; Actions vuelve a compilar y probar, genera `manifest.json` y crea el Release con un archivo por plataforma.

El manifest registra las versiones de whisper.cpp y FFmpeg, y para cada paquete: OS, arquitectura, nombre, tamaño, SHA-256 y rutas internas de `whisper-cli` y `ffmpeg`. Los paquetes Windows son `.zip`; macOS y Linux usan `.tar.gz`.

## Licencias

- Los scripts propios de este repositorio: MIT, ver [`LICENSE`](LICENSE).
- whisper.cpp: MIT. Cada paquete incluye el texto de licencia de la versión empaquetada.
- FFmpeg: LGPL-2.1-or-later. Cada paquete incluye el texto de licencia, la versión exacta, la línea de configuración utilizada y el enlace al código fuente.
- La muestra de voz de prueba está generada con eSpeak NG y se publica bajo CC0; su texto, comando de generación y licencia están en [`testdata/README.md`](testdata/README.md).
