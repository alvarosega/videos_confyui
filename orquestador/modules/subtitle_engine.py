import json
import re
import wave
from pathlib import Path
import spacy
from deep_translator import GoogleTranslator

from config import INPUT_DIR, OUTPUT_DIR
from core.storage_engine import StorageEngine


class SubtitleEngine:
    """
    Fase 6: Generación de 3 pistas SRT maestras sin solapamiento temporal.
    Usa estrictamente {escena_id}_words.json como fuente de la verdad.
    """

    def __init__(self, storage_engine: StorageEngine, proyecto_id: str):
        self.storage = storage_engine
        self.proyecto_id = proyecto_id

        self.audios_dir = INPUT_DIR / proyecto_id / "audios"
        self.subtitulos_dir = OUTPUT_DIR / proyecto_id / "subtitles"
        self.subtitulos_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.nlp = spacy.load("es_core_news_md")
        except Exception:
            self.nlp = None
            print("[SubtitleEngine] ADVERTENCIA: spaCy 'es_core_news_md' no encontrado.")

        self.translator = GoogleTranslator(source='es', target='en')

    def _obtener_duracion_audio(self, escena_id: str, duracion_config: float = 0.0) -> float:
        ruta_wav = self.audios_dir / f"{escena_id}.wav"
        if ruta_wav.exists():
            try:
                with wave.open(str(ruta_wav), "rb") as wf:
                    return wf.getnframes() / float(wf.getframerate())
            except Exception as e:
                print(f"[SubtitleEngine] Error leyendo WAV {ruta_wav.name}: {e}")
        return duracion_config if duracion_config > 0.0 else 4.0

    def _formatear_tiempo_srt(self, segundos: float) -> str:
        """Formatea segundos float a estándar estricto SRT: HH:MM:SS,mmm"""
        segundos = max(0.0, segundos)
        horas = int(segundos // 3600)
        minutos = int((segundos % 3600) // 60)
        segs = int(segundos % 60)
        milis = int(round((segundos - int(segundos)) * 1000))
        if milis >= 1000:
            milis = 999
        return f"{horas:02d}:{minutos:02d}:{segs:02d},{milis:03d}"

    def _limpiar_palabra(self, palabra: str) -> str:
        return re.sub(r'^[^\wáéíóúÁÉÍÓÚñÑüÜ]+|[^\wáéíóúÁÉÍÓÚñÑüÜ]+$', '', palabra)

    def _es_palabra_clave(self, token) -> bool:
        """Criterio de Highlight: Verbos en infinitivo, nombres propios o términos relevantes."""
        if token.pos_ == "VERB" and token.morph.get("VerbForm") == ["Inf"]:
            return True
        if token.pos_ in ["PROPN", "NUM"]:
            return True
        if token.pos_ == "NOUN" and len(token.text) >= 7:
            return True
        return False

    def _cargar_palabras_json(self, escena_id: str, dialogo: str, duracion_wav: float) -> list[dict]:
        """Extrae los tiempos directos del JSON generado por Kokoro."""
        ruta_json = self.audios_dir / f"{escena_id}_words.json"
        palabras_data = []

        if ruta_json.exists():
            try:
                with open(ruta_json, "r", encoding="utf-8") as jf:
                    palabras_data = json.load(jf)
            except Exception as e:
                print(f"[SubtitleEngine] Error leyendo JSON {escena_id}: {e}")

        # Fallback de emergencia solo si no existe el JSON
        if not palabras_data:
            palabras_raw = [self._limpiar_palabra(p) for p in dialogo.strip().split() if self._limpiar_palabra(p)]
            if not palabras_raw:
                return []
            
            offset_ini = 0.12
            dur_voz = max(0.1, duracion_wav - 0.32)
            pesos = [max(2, len(p)) for p in palabras_raw]
            peso_tot = sum(pesos)
            cur = offset_ini

            for p, peso in zip(palabras_raw, pesos):
                dur_p = (peso / peso_tot) * dur_voz
                palabras_data.append({
                    "word": p,
                    "start": round(cur, 3),
                    "end": round(cur + dur_p, 3)
                })
                cur += dur_p

        # Clasificación posicional 1:1 con spaCy
        if self.nlp:
            doc = self.nlp(dialogo)
            tokens_validos = [t for t in doc if self._limpiar_palabra(t.text)]
            for i, item in enumerate(palabras_data):
                if i < len(tokens_validos):
                    item["is_highlight"] = self._es_palabra_clave(tokens_validos[i])
                else:
                    w = item["word"].lower()
                    item["is_highlight"] = w.endswith(("ar", "er", "ir")) and len(w) > 4
        else:
            for item in palabras_data:
                w = item["word"].lower()
                item["is_highlight"] = w.endswith(("ar", "er", "ir")) and len(w) > 4

        return palabras_data

    def _generar_palabras_ingles(self, dialogo_es: str, t_inicio_escena: float, t_fin_escena: float) -> list[dict]:
        """Traduce al inglés y reparte exactamente en la ventana temporal activa."""
        duracion_total = max(0.1, t_fin_escena - t_inicio_escena)
        try:
            traduccion = self.translator.translate(dialogo_es)
        except Exception:
            traduccion = dialogo_es

        palabras_en = [self._limpiar_palabra(p) for p in traduccion.strip().split() if self._limpiar_palabra(p)]
        if not palabras_en:
            return []

        pesos = [max(2, len(p)) for p in palabras_en]
        peso_total = sum(pesos)
        cursor = t_inicio_escena
        palabras_en_data = []

        for p, peso in zip(palabras_en, pesos):
            dur_p = (peso / peso_total) * duracion_total
            palabras_en_data.append({
                "word": p,
                "start": round(cursor, 3),
                "end": round(cursor + dur_p, 3)
            })
            cursor += dur_p

        return palabras_en_data

    def generar_subtitulos_timeline_completo(self) -> dict[str, Path]:
        """Genera las 3 pistas maestras alineadas al timeline global sin colisiones."""
        config = self.storage.cargar_config(self.proyecto_id)
        escenas = config.get("escenas", [])
        if not escenas:
            raise ValueError("No hay escenas registradas en la configuración.")

        entradas_normal = []
        entradas_highlights = []
        entradas_en = []

        tiempo_acumulado_global = 0.0
        idx_normal = 1
        idx_high = 1
        idx_en = 1

        for escena in escenas:
            e_id = escena["id"]
            dialogo = escena.get("dialogo", "").strip()
            duracion_wav = self._obtener_duracion_audio(e_id, escena.get("duracion_audio", 0.0))

            if dialogo:
                # 1. Cargar timestamps exactos del JSON de Kokoro
                palabras_es = self._cargar_palabras_json(e_id, dialogo, duracion_wav)

                if palabras_es:
                    # 2. Asignación exclusiva Normal vs Highlights (con guarda de 1ms)
                    for item in palabras_es:
                        t_in = item["start"] + tiempo_acumulado_global
                        # Restar 1ms al t_out para evitar solapamiento de frame en DaVinci
                        t_out = max(t_in + 0.05, item["end"] + tiempo_acumulado_global - 0.001)

                        t_in_srt = self._formatear_tiempo_srt(t_in)
                        t_out_srt = self._formatear_tiempo_srt(t_out)
                        word = item["word"]

                        if item.get("is_highlight", False):
                            entradas_highlights.append(f"{idx_high}\n{t_in_srt} --> {t_out_srt}\n{word}\n")
                            idx_high += 1
                        else:
                            entradas_normal.append(f"{idx_normal}\n{t_in_srt} --> {t_out_srt}\n{word}\n")
                            idx_normal += 1

                    # 3. Pista en Inglés (usando ventana activa real de la escena)
                    t_ini_activa = palabras_es[0]["start"] + tiempo_acumulado_global
                    t_fin_activa = palabras_es[-1]["end"] + tiempo_acumulado_global
                    palabras_en = self._generar_palabras_ingles(dialogo, t_ini_activa, t_fin_activa)

                    for item in palabras_en:
                        t_in = item["start"]
                        t_out = max(t_in + 0.05, item["end"] - 0.001)
                        t_in_srt = self._formatear_tiempo_srt(t_in)
                        t_out_srt = self._formatear_tiempo_srt(t_out)
                        entradas_en.append(f"{idx_en}\n{t_in_srt} --> {t_out_srt}\n{item['word']}\n")
                        idx_en += 1

            tiempo_acumulado_global += duracion_wav

        # Guardar los 3 archivos maestros .SRT
        ruta_normal = self.subtitulos_dir / f"{self.proyecto_id}_normal.srt"
        ruta_highlights = self.subtitulos_dir / f"{self.proyecto_id}_highlights.srt"
        ruta_en = self.subtitulos_dir / f"{self.proyecto_id}_en.srt"

        with open(ruta_normal, "w", encoding="utf-8") as f:
            f.write("\n".join(entradas_normal))

        with open(ruta_highlights, "w", encoding="utf-8") as f:
            f.write("\n".join(entradas_highlights))

        with open(ruta_en, "w", encoding="utf-8") as f:
            f.write("\n".join(entradas_en))

        print(f"\n[SubtitleEngine] [ÉXITO] Pistas maestras generadas en: {self.subtitulos_dir}")
        print(f" -> Normal (ES): {ruta_normal.name} ({idx_normal - 1} palabras)")
        print(f" -> Highlights (ES): {ruta_highlights.name} ({idx_high - 1} palabras)")
        print(f" -> English (EN): {ruta_en.name} ({idx_en - 1} palabras)")
        print(f" -> Duración total: {self._formatear_tiempo_srt(tiempo_acumulado_global)}")

        return {"normal": ruta_normal, "highlights": ruta_highlights, "en": ruta_en}