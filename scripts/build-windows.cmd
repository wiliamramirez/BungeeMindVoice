@echo off
setlocal
cd /d "%~dp0\.."
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (
  echo Visual Studio 2022 no esta instalado.
  exit /b 1
)
call "%VSROOT%\Common7\Tools\VsDevCmd.bat" -arch=%~2 -host_arch=%~3
if errorlevel 1 exit /b %errorlevel%
where ninja >nul 2>nul
if errorlevel 1 (
  echo Ninja no esta instalado en el runner.
  exit /b 1
)
where clang-cl >nul 2>nul
if errorlevel 1 (
  echo clang-cl no esta instalado en el runner.
  exit /b 1
)
where cl >nul 2>nul
if errorlevel 1 (
  echo cl.exe no esta disponible despues de VsDevCmd.
  exit /b 1
)
set "BMV_MSVC_BIN=%VCToolsInstallDir%bin\Host%~3\%~2"
if not exist "%BMV_MSVC_BIN%\link.exe" (
  echo No se encontro link.exe de MSVC en "%BMV_MSVC_BIN%".
  exit /b 1
)
python scripts\build.py --target %~1 --output dist\%~1
exit /b %errorlevel%
