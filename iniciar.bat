@echo off
chcp 65001 >nul
title Pipeline de Video IA - Panel de Control Unificado

:: Definicion de rutas base
set "ROOT_DIR=%~dp0"
set "PYTHON_COMFY=C:\Users\SEGA\miniconda3\envs\env_comfyui\python.exe"
set "PYTHON_ORQ=C:\Users\SEGA\miniconda3\envs\orquestador_env\python.exe"

:MENU
cls
echo ===============================================================================
echo                PANEL DE CONTROL CENTRAL - PIPELINE DE VIDEO IA
echo ===============================================================================
echo.
echo   [1] 🌐 Iniciar INTERFAZ WEB COMPLETA (Recomendado)
echo       - Abre ComfyUI Server (127.0.0.1:8188) y Studio Web (127.0.0.1:7860)
echo.
echo   [2] 💻 Iniciar SOLO ComfyUI Server Backend
echo       - http://127.0.0.1:8188 (Motor de renderizado SDXL/LivePortrait)
echo.
echo   [3] 🖥️ Iniciar SOLO Studio Web (Gradio)
echo       - http://127.0.0.1:7860 (Interfaz visual del orquestador)
echo.
echo   [4] ⌨️ Iniciar Orquestador por Consola Terminal (CLI)
echo       - Modo interactivo clasico por comandos
echo.
echo   [0] 🚪 Salir
echo.
echo ===============================================================================
set /p OPCION=" Seleccione una opción [0-4]: "

if "%OPCION%"=="1" goto START_ALL
if "%OPCION%"=="2" goto START_COMFY
if "%OPCION%"=="3" goto START_WEB
if "%OPCION%"=="4" goto START_CLI
if "%OPCION%"=="0" exit /b 0
goto MENU

:START_ALL
echo.
echo [1/2] Iniciando ComfyUI Server en segundo plano...
start "ComfyUI Server Backend (8188)" /d "%ROOT_DIR%ComfyUI" "%PYTHON_COMFY%" main.py --listen 127.0.0.1 --port 8188 --preview-method auto

echo [INFO] Esperando inicializacion de servicios (3 segundos)...
timeout /t 3 /nobreak >nul

echo [2/2] Iniciando Studio Web (7860)...
start "Studio Web Orquestador (7860)" /d "%ROOT_DIR%orquestador" "%PYTHON_COMFY%" app_web.py

echo.
echo [✓] Ambos servicios han sido lanzados en sus ventanas correspondientes.
echo     - ComfyUI:   http://127.0.0.1:8188
echo     - Studio Web: http://127.0.0.1:7860
echo.
pause
goto MENU

:START_COMFY
echo.
echo Iniciando ComfyUI Server Backend en esta ventana...
cd /d "%ROOT_DIR%ComfyUI"
if exist "%PYTHON_COMFY%" (
    "%PYTHON_COMFY%" main.py --listen 127.0.0.1 --port 8188 --preview-method auto
) else (
    python main.py --listen 127.0.0.1 --port 8188 --preview-method auto
)
pause
goto MENU

:START_WEB
echo.
echo Iniciando Studio Web en esta ventana...
cd /d "%ROOT_DIR%orquestador"
if exist "%PYTHON_COMFY%" (
    "%PYTHON_COMFY%" app_web.py
) else (
    python app_web.py
)
pause
goto MENU

:START_CLI
echo.
echo Iniciando Orquestador CLI en esta ventana...
cd /d "%ROOT_DIR%orquestador"
if exist "%PYTHON_ORQ%" (
    "%PYTHON_ORQ%" main.py
) else (
    python main.py
)
pause
goto MENU
