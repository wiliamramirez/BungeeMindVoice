# BungeeMind Voice

Binarios portables de voz que BungeeMind descarga y verifica para transcribir audio localmente. Este repositorio contiene scripts de build y paquetes de software libre de terceros; no contiene código de BungeeMind.

## Plataformas

Cada Release publica un archivo por plataforma. Los nombres `os` y `arch` del manifest son estables: `macos`, `windows` o `linux`, y `arm64` o `x86_64`.

| OS | Arquitectura | Runner de Actions | Base mínima |
| --- | --- | --- | --- |
| macOS | arm64 | `macos-15` | macOS 11.0 |
| macOS | x86_64 | `macos-15-intel` | macOS 10.13 |
| Windows | x86_64 | `windows-2025` | Windows x64 |
| Windows | arm64 | `windows-11-arm` | Windows ARM64 |
| Linux | x86_64 | `ubuntu-22.04` | glibc 2.35 |
| Linux | arm64 | `ubuntu-22.04-arm` | glibc 2.35 |

Los binarios x86_64 de whisper.cpp usan AVX2, FMA y F16C; requieren una CPU x86-64-v3. Los binarios arm64 usan el baseline ARMv8-A, sin optimizaciones específicas del runner. En macOS, Metal está activado y su biblioteca queda embebida en `whisper-cli`.

## Contenido y versiones

Las versiones, URL y SHA-256 de los tarballs fuente están centralizados en [`pins.json`](pins.json). El build verifica cada hash antes de extraer o compilar. La primera versión planeada usa whisper.cpp v1.9.4 y FFmpeg 9.0.2.

Cada paquete contiene `whisper-cli`, `ffmpeg` y sus licencias. FFmpeg se configura como LGPL-2.1-or-later, estático, sin autodetección, sin red y con solo los componentes de audio necesarios para Ogg/Opus, Ogg/Vorbis, MP3, M4A/AAC, FLAC y WAV. Convierte al formato WAV PCM de 16 bits, mono y 16 kHz que consume BungeeMind.

## Publicar

`workflow_dispatch` compila, ejecuta la prueba de transcripción en los seis runners y deja los paquetes como artefactos, sin crear un Release. Para publicar, crea y sube un tag estable `vX.Y.Z`; Actions vuelve a compilar y probar, genera `manifest.json` y crea el Release con un archivo por plataforma.

El manifest registra las versiones de whisper.cpp y FFmpeg, y para cada paquete: OS, arquitectura, nombre, tamaño, SHA-256 y rutas internas de `whisper-cli` y `ffmpeg`. Los paquetes Windows son `.zip`; macOS y Linux usan `.tar.gz`.

## Licencias

- Los scripts propios de este repositorio: MIT, ver [`LICENSE`](LICENSE).
- whisper.cpp: MIT. Cada paquete incluye el texto de licencia de la versión empaquetada.
- FFmpeg: LGPL-2.1-or-later. Cada paquete incluye el texto de licencia, la versión exacta, la línea de configuración utilizada y el enlace al código fuente.
- La muestra de voz de prueba está generada con eSpeak NG y se publica bajo CC0; su texto, comando de generación y licencia están en [`testdata/README.md`](testdata/README.md).
