@echo off
setlocal

title Instalador de Requisitos - YT Downloader
echo ================================================
echo   Instalador de Requisitos - Descargar-videos
echo ================================================
echo.

REM Detectar Python (preferir py launcher)
set "PY_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] No se encontro Python en el sistema.
    echo Instala Python 3 y marca la opcion "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [INFO] Python detectado correctamente.
echo [INFO] Actualizando pip...
%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] No se pudo actualizar pip.
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Instalando dependencias de Python...
if exist requirements.txt (
    %PY_CMD% -m pip install -r requirements.txt
) else (
    %PY_CMD% -m pip install yt-dlp
)

if errorlevel 1 (
    echo [ERROR] Ocurrio un problema al instalar dependencias.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Dependencias de Python instaladas correctamente.
echo.
echo [IMPORTANTE] Tambien necesitas FFmpeg para MP3/MP4.
echo - Si ya esta instalado y en PATH, no debes hacer nada.
echo - Si no, descargalo desde: https://ffmpeg.org/download.html
echo.
echo Instalacion finalizada.
pause
exit /b 0
