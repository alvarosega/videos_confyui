@echo off
title ComfyUI Server (Pipeline Videos)
echo ========================================================
echo  Iniciando ComfyUI Server con Entorno Conda: env_comfyui
echo  Aceleracion: NVIDIA GeForce RTX 4070 Laptop GPU (CUDA 12.1)
echo  Endpoint: http://127.0.0.1:8188
echo ========================================================

cd /d "%~dp0ComfyUI"

set "PYTHON_EXE=C:\Users\SEGA\miniconda3\envs\env_comfyui\python.exe"

if exist "%PYTHON_EXE%" (
    echo [INFO] Detectado entorno dedicado: env_comfyui
    "%PYTHON_EXE%" main.py --listen 127.0.0.1 --port 8188 --preview-method auto
) else (
    echo [ADVERTENCIA] No se encontro %PYTHON_EXE%. Intentando con python del PATH...
    python main.py --listen 127.0.0.1 --port 8188 --preview-method auto
)

pause
