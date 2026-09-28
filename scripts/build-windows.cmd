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
python scripts\build.py --target %~1 --output dist\%~1
exit /b %errorlevel%
