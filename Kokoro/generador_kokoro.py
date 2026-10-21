import sys
import argparse
import json
import re
import soundfile as sf
import numpy as np
import warnings
import torch
import torchaudio.functional as F
from pathlib import Path
from kokoro import KPipeline

warnings.filterwarnings("ignore")


def limpiar_palabra(palabra: str) -> str:
    return re.sub(r'^[^\wáéíóúÁÉÍÓÚñÑüÜ]+|[^\wáéíóúÁÉÍÓÚñÑüÜ]+$', '', palabra)


def aplicar_fade_final(audio: np.ndarray, num_muestras: int = 480) -> np.ndarray:
    """Aplica fade-in y fade-out de 10ms a 48kHz únicamente a los extremos del archivo final."""
    if len(audio) < num_muestras * 2:
        return audio
    audio_out = audio.copy()
    fade_in = np.linspace(0.0, 1.0, num_muestras, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, num_muestras, dtype=np.float32)
    audio_out[:num_muestras] *= fade_in
    audio_out[-num_muestras:] *= fade_out
    return audio_out


def resolver_voz(pipeline: KPipeline, spec_voz: str):
    """
    Resuelve una voz individual o realiza Voice Blending (combinación lineal de tensores).
    Ejemplos de spec_voz válidos:
      - 'em_alex'
      - 'am_fenrir'
      - 'em_alex:0.6+am_fenrir:0.4'
      - 'em_alex:0.5+am_onyx:0.3+bm_george:0.2'
    """
    spec_voz = spec_voz.strip()
    
    # Caso 1: Voz simple sin mezcla
    if "+" not in spec_voz and ":" not in spec_voz:
        return spec_voz

    # Caso 2: Voice Blending ponderado
    partes = spec_voz.split("+")
    tensores = []
    pesos = []

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if ":" in parte:
            nombre_voz, str_peso = parte.split(":", 1)
            try:
                peso = float(str_peso.strip())
            except ValueError:
                peso = 1.0
        else:
            nombre_voz = parte
            peso = 1.0

        nombre_voz = nombre_voz.strip()
        tensor_voz = pipeline.load_voice(nombre_voz)
        tensores.append(tensor_voz)
        pesos.append(peso)

    if not tensores:
        return "em_alex"

    peso_total = sum(pesos)
    if peso_total <= 0:
        peso_total = 1.0

    # Combinación lineal normalizada de embeddings
    voz_mezclada = sum((w / peso_total) * t for w, t in zip(pesos, tensores))
    return voz_mezclada


def main():
    parser = argparse.ArgumentParser(description="Generador TTS con Kokoro-82M y Sincronización")
    parser.add_argument("--texto", type=str, required=True, help="Texto a sintetizar")
    parser.add_argument("--voz", type=str, required=True, help="ID de voz o fórmula de mezcla")
    parser.add_argument("--salida", type=str, required=True, help="Ruta de salida .wav")
    parser.add_argument("--velocidad", type=float, default=1.05, help="Velocidad calibrada")
    args = parser.parse_args()

    texto_limpio = args.texto.strip()
    if not texto_limpio:
        print("[KOKORO ERROR] El texto está vacío.")
        sys.exit(1)

    # Inyección de token de guarda fonética para evitar truncamiento inicial de sílabas
    texto_input = f"— {texto_limpio}"

    try:
        pipeline = KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M')
        orig_sample_rate = 24000
        target_sample_rate = 48000

        voz_final = resolver_voz(pipeline, args.voz)

        # Margen de silencio absoluto inicial y final
        duracion_silencio_inicial = 0.10
        duracion_silencio_final = 0.20
        silencio_inicial = np.zeros(int(orig_sample_rate * duracion_silencio_inicial), dtype=np.float32)
        silencio_final = np.zeros(int(orig_sample_rate * duracion_silencio_final), dtype=np.float32)

        audio_chunks = [silencio_inicial]
        words_metadata = []
        cursor_tiempo = duracion_silencio_inicial

        generator = pipeline(texto_input, voice=voz_final, speed=args.velocidad)

        for gs, ps, audio in generator:
            if audio is None or len(audio) == 0:
                continue

            if isinstance(audio, torch.Tensor):
                audio_np = audio.detach().cpu().numpy().astype(np.float32)
            else:
                audio_np = np.array(audio, dtype=np.float32)

            audio_chunks.append(audio_np)
            duracion_chunk = len(audio_np) / float(orig_sample_rate)

            # Extraer palabras ignorando el token de guarda inicial
            palabras_raw = [limpiar_palabra(p) for p in gs.strip().split() if limpiar_palabra(p)]
            if palabras_raw:
                pesos = [max(2, len(p)) for p in palabras_raw]
                peso_total = sum(pesos)
                t_acum = cursor_tiempo

                for p, peso in zip(palabras_raw, pesos):
                    dur_p = (peso / peso_total) * duracion_chunk
                    t_fin = t_acum + dur_p
                    words_metadata.append({
                        "word": p,
                        "start": round(t_acum, 3),
                        "end": round(t_fin, 3)
                    })
                    t_acum = t_fin

            cursor_tiempo += duracion_chunk

        audio_chunks.append(silencio_final)

        if len(audio_chunks) <= 2:
            print("[KOKORO ERROR] Inferencia vacía.")
            sys.exit(1)

        # Concatenación en 24kHz
        final_audio_24k = np.concatenate(audio_chunks)

        # Remuestreo a 48kHz para el pipeline de video
        audio_tensor = torch.from_numpy(final_audio_24k).float()
        resampled_tensor = F.resample(audio_tensor, orig_freq=orig_sample_rate, new_freq=target_sample_rate)
        final_audio_48k = resampled_tensor.numpy()

        # Fade final
        final_audio_48k = aplicar_fade_final(final_audio_48k)

        # Guardar audio WAV
        sf.write(args.salida, final_audio_48k, target_sample_rate)

        # Guardar metadatos JSON
        ruta_salida = Path(args.salida)
        ruta_json = ruta_salida.parent / f"{ruta_salida.stem}_words.json"
        with open(ruta_json, "w", encoding="utf-8") as jf:
            json.dump(words_metadata, jf, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[KOKORO ERROR] Falló la inferencia: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()