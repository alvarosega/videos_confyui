import os
import re
import asyncio
import edge_tts
from mutagen.mp3 import MP3

VOZ = "es-MX-JorgeNeural"
RUTA_GUION = r"C:\ia-video\orquestador\guion.txt"
CARPETA_AUDIOS = r"C:\ia-video\orquestador\audios"
FPS_BASE = 16

os.makedirs(CARPETA_AUDIOS, exist_ok=True)

async def generar_audio_escena(texto: str, ruta_salida: str):
    communicate = edge_tts.Communicate(texto, VOZ, rate="+0%", pitch="+0Hz")
    await communicate.save(ruta_salida)

def obtener_duracion_mp3(ruta_audio: str) -> float:
    audio = MP3(ruta_audio)
    return audio.info.length

def calcular_frames(duracion_segundos: float, fps: int = 16) -> int:
    frames_teoricos = int(round(duracion_segundos * fps))
    # AnimateDiff requiere múltiplos de 8 y un mínimo de 16 frames para estabilidad de memoria
    frames_ajustados = max(16, (frames_teoricos + 7) & ~7)
    return frames_ajustados

async def procesar_guion():
    if not os.path.exists(RUTA_GUION):
        print(f"Error: No se encontró el archivo {RUTA_GUION}")
        return []

    with open(RUTA_GUION, "r", encoding="utf-8") as f:
        lineas = [linea.strip() for linea in f.readlines() if linea.strip()]

    escenas_procesadas = []

    for idx, texto_escena in enumerate(lineas, start=1):
        nombre_audio = f"escena_{idx:03d}.mp3"
        ruta_audio = os.path.join(CARPETA_AUDIOS, nombre_audio)
        
        await generar_audio_escena(texto_escena, ruta_audio)
        duracion = obtener_duracion_mp3(ruta_audio)
        frames = calcular_frames(duracion, FPS_BASE)

        datos_escena = {
            "id": idx,
            "texto": texto_escena,
            "archivo_audio": ruta_audio,
            "duracion_segundos": round(duracion, 2),
            "frames_comfyui": frames
        }
        escenas_procesadas.append(datos_escena)
        print(f"[Escena {idx:02d}] Audio: {nombre_audio} | Duración: {round(duracion, 2)}s | Frames ComfyUI: {frames}")

    return escenas_procesadas

if __name__ == "__main__":
    print("Iniciando procesamiento de guion y generación de audios...")
    resultado = asyncio.run(procesar_guion())
    print("\nProcesamiento completado con éxito.")