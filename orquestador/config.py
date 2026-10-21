import os
from pathlib import Path

# Detección dinámica de la raíz (C:\ia-video)
BASE_DIR = Path(__file__).resolve().parent.parent

# Rutas de subsistemas
ORQUESTADOR_DIR = BASE_DIR / "orquestador"
COMFYUI_DIR = BASE_DIR / "ComfyUI"

# Rutas operativas de ComfyUI
INPUT_DIR = COMFYUI_DIR / "input" / "projects"
OUTPUT_DIR = COMFYUI_DIR / "output" / "projects"

# Rutas del orquestador
PRESETS_DIR = ORQUESTADOR_DIR / "presets"
MODULES_DIR = ORQUESTADOR_DIR / "modules"

# API de ComfyUI
COMFYUI_SERVER_URL = "127.0.0.1:8188"