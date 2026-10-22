@echo off
title Orquestador de Videos IA
echo ========================================================
echo  Iniciando Orquestador con Entorno Conda: orquestador_env
echo  Controlador CLI del Pipeline
echo ========================================================

cd /d "%~dp0orquestador"

set "PYTHON_EXE=C:\Users\SEGA\miniconda3\envs\orquestador_env\python.exe"

if exist "%PYTHON_EXE%" (
    echo [INFO] Detectado entorno dedicado: orquestador_env
    "%PYTHON_EXE%" main.py
) else (
    echo [ADVERTENCIA] No se encontro %PYTHON_EXE%. Intentando con python del PATH...
    python main.py
)

pause
