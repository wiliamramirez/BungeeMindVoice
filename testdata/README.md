# Prueba de transcripción

`speech-test.ogg` es una grabación sintética mono Ogg/Opus con la frase en inglés “Hello. This is a short speech recognition test.” El texto de la prueba es propio y el archivo de audio se publica bajo CC0-1.0.

Se generó con eSpeak NG 1.52.0, software GPL-3.0-or-later, y FFmpeg/libopus. Para regenerarlo con esas herramientas:

```sh
espeak-ng -v en-us -s 135 -w /tmp/bungeemind-voice-test.wav "Hello. This is a short speech recognition test."
ffmpeg -y -loglevel error -i /tmp/bungeemind-voice-test.wav -c:a libopus -b:a 24k testdata/speech-test.ogg
```

Licencia de eSpeak NG: <https://github.com/espeak-ng/espeak-ng/blob/master/COPYING>. El programa se usa únicamente para generar el fixture; no se incluye en los paquetes.
