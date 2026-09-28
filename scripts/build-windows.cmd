@echo off
setlocal
cd /d "%~dp0\.."
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (
  echo Visual Studio 2022 no esta instalado.
  exit /b 1
)
set "TARGET_ARCH=%~2"
set "HOST_ARCH=%~3"
if /I "%TARGET_ARCH%"=="ARM64" set "TARGET_ARCH=arm64"
if /I "%TARGET_ARCH%"=="X64" set "TARGET_ARCH=x64"
if /I "%TARGET_ARCH%"=="AMD64" set "TARGET_ARCH=amd64"
if /I "%HOST_ARCH%"=="ARM64" set "HOST_ARCH=arm64"
if /I "%HOST_ARCH%"=="X64" set "HOST_ARCH=x64"
if /I "%HOST_ARCH%"=="AMD64" set "HOST_ARCH=amd64"
call "%VSROOT%\Common7\Tools\VsDevCmd.bat" -arch=%TARGET_ARCH% -host_arch=%HOST_ARCH%
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
set "TARGET_DIR=%TARGET_ARCH%"
set "HOST_DIR=%HOST_ARCH%"
if /I "%TARGET_ARCH%"=="amd64" set "TARGET_DIR=x64"
if /I "%HOST_ARCH%"=="amd64" set "HOST_DIR=x64"
set "BMV_MSVC_BIN=%VCToolsInstallDir%bin\Host%HOST_DIR%\%TARGET_DIR%"
if not exist "%BMV_MSVC_BIN%\link.exe" (
  echo No se encontro link.exe de MSVC en "%BMV_MSVC_BIN%".
  exit /b 1
)
set "SDK_UM_DIR=%WindowsSdkDir%Lib\%WindowsSDKVersion%um\%TARGET_DIR%"
set LIB | findstr /I /L /C:"%SDK_UM_DIR%" >nul
if errorlevel 1 (
  echo LIB no contiene la carpeta de bibliotecas UM del Windows SDK para %TARGET_ARCH%: "%SDK_UM_DIR%".
  exit /b 1
)
python scripts\build.py --target %~1 --output dist\%~1
exit /b %errorlevel%
