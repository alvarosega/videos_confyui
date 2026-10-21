@echo off
title ComfyUI Server (Pipeline Videos)
echo ========================================================
echo  Iniciando ComfyUI Server para Pipeline de Video
echo  Optimizacion: 8GB VRAM (NVIDIA RTX 4070 Laptop)
echo  Endpoint: http://127.0.0.1:8188
echo ========================================================

cd /d "%~dp0ComfyUI"

:: Argumentos recomendados para 8GB VRAM:
:: --listen 127.0.0.1 : Escucha local en el puerto del orquestador
:: --port 8188        : Puerto por defecto esperado por conector y core
:: --preview-method auto : Previsualizacion eficiente
python main.py --listen 127.0.0.1 --port 8188 --preview-method auto

pause
