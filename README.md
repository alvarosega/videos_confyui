# videos_confyui

Pipeline modular para generación automatizada de video con IA que orquesta ComfyUI, generación de audio (Kokoro TTS), animación facial (SadTalker) y pipelines de renderizado.

## Arquitectura de Módulos

El repositorio integra 4 submódulos principales:

1. **`orquestador/`**
   - Motor central en Python encargado de coordinar todo el flujo:
     - `conector_comfyui.py`: Cliente API para comunicación con ComfyUI.
     - `project_manager.py`: Gestión de proyectos, guiones y estructuras de escenas.
     - `modulo_audio.py`: Procesamiento y alineación de audios.
     - `modules/` & `presets/`: Configuraciones de cámara, generación de imágenes, motion y estilos.

2. **`ComfyUI/`**
   - Contiene las plantillas de workflows y proyectos de requests:
     - `input/projects/`: Guiones (`guion.json`), configuraciones de escena (`project_config.json`) y plantillas de workflows (`templates/wf_*.json`).
     - Workflows base en formato JSON.
   - *Nota*: Modelos IA (`.safetensors`), imágenes y videos generados se excluyen del repositorio y se gestionan localmente.

3. **`Kokoro/`**
   - `generador_kokoro.py`: Módulo para síntesis de voz (TTS) de alta fidelidad para las narraciones.

4. **`SadTalker/`**
   - Pipeline adaptado para generación de animación facial y sincronización labial (Lip-sync).

---

## Requisitos y Configuración Local

1. **Dependencias:**
   - Python 3.10+
   - PyTorch con soporte CUDA

2. **Modelos y Checkpoints:**
   - Los pesos y checkpoints para ComfyUI y SadTalker deben descargarse en sus respectivas carpetas `models/` y `checkpoints/`.
