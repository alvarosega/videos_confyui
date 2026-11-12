@echo off
title Orquestador de Video IA - Studio Web
echo ========================================================
echo  Iniciando Interfaz Web del Orquestador (Gradio)
echo  Entorno Conda: env_comfyui
echo  URL Local: http://127.0.0.1:7860
echo ========================================================

cd /d "%~dp0orquestador"

set "PYTHON_EXE=C:\Users\SEGA\miniconda3\envs\env_comfyui\python.exe"

if exist "%PYTHON_EXE%" (
    echo [INFO] Iniciando Studio Web con entorno: env_comfyui
    "%PYTHON_EXE%" app_web.py
) else (
    echo [ADVERTENCIA] No se encontro %PYTHON_EXE%. Intentando con python del PATH...
    python app_web.py
)

pause
