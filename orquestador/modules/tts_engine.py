import os
import subprocess
import wave
import re
from pathlib import Path
from config import INPUT_DIR


class TTSEngine:
    """
    Fase 2: Generación de audio mediante Kokoro-82M (Local).
    Soporta todo el catálogo nativo y cross-language de Kokoro, así como
    fórmulas de Voice Blending (mezcla de tensores de voz) definidas en guion.json.
    """

    VOZ_FALLBACK_HOMBRE = "em_alex"
    VOZ_FALLBACK_MUJER = "ef_dora"

    # Biblioteca completa de voces disponibles en Kokoro-82M
    VOCES_DISPONIBLES = {
        # Español (Nativas)
        "espanol": {
            "em_alex": "Español Masculino Neutro / Estándar",
            "em_santa": "Español Masculino Maduro / Grave",
            "ef_dora": "Español Femenino Neutro / Natural",
        },
        # Inglés Americano (Cross-Language recomendado para tonos profundos/oscuros)
        "ingles_americano": {
            "am_fenrir": "Masculino Grave / Autoritario / Frio (Ideal Terror)",
            "am_onyx": "Masculino Oscuro / Sobrio / Denso",
            "am_michael": "Masculino Profesional / Seco / Corporativo",
            "am_eric": "Masculino Táctico / Institucional",
            "am_adam": "Masculino Directo / Equilibrado",
            "am_echo": "Masculino Articulado",
            "am_liam": "Masculino Joven / Neutro",
            "am_puck": "Masculino Enérgico / Dinámico",
            "am_santa": "Masculino Cálido / Profundo",
            "af_heart": "Femenino Cálido / Principal",
            "af_nicole": "Femenino Serio / Analítico / Controlado",
            "af_bella": "Femenino Natural / Expresivo",
            "af_sarah": "Femenino Firme / Corporativo",
            "af_sky": "Femenino Suave / Aireado",
            "af_alloy": "Femenino Neutro / Moderno",
            "af_aoede": "Femenino Resonante",
            "af_jessica": "Femenino Claro",
            "af_kore": "Femenino Maduro",
            "af_nova": "Femenino Dinámico",
            "af_river": "Femenino Calmo",
        },
        # Inglés Británico (Cross-Language formal / distante)
        "ingles_britanico": {
            "bm_george": "Masculino Formal / Distante / Aristocrático",
            "bm_daniel": "Masculino Serio / Periodístico",
            "bm_fable": "Masculino Narrativo",
            "bm_lewis": "Masculino Articulado",
            "bf_alice": "Femenino Formal / Educado",
            "bf_emma": "Femenino Distante / Analítico",
            "bf_isabella": "Femenino Cálido",
            "bf_lily": "Femenino Joven",
        },
        # Italiano (Alta compatibilidad fonética con español)
        "italiano": {
            "im_nicola": "Italiano Masculino / Cadencia Rápida",
            "if_sara": "Italiano Femenino / Melódico",
        },
        # Portugués
        "portugues": {
            "pm_alex": "Portugués Masculino Neutro",
            "pm_santa": "Portugués Masculino Grave",
            "pf_dora": "Portugués Femenino Neutro",
        },
        # Francés
        "frances": {
            "ff_siwis": "Francés Femenino / Articulado",
        },
        # Hindi
        "hindi": {
            "hm_omega": "Hindi Masculino Profundo",
            "hm_psi": "Hindi Masculino Estándar",
            "hf_alpha": "Hindi Femenino",
            "hf_beta": "Hindi Femenino Expresivo",
        },
        # Japonés
        "japones": {
            "jm_kumo": "Japonés Masculino",
            "jf_alpha": "Japonés Femenino",
            "jf_gongitsune": "Japonés Femenino Tradicional",
            "jf_nezumi": "Japonés Femenino Rápido",
            "jf_tebukuro": "Japonés Femenino Suave",
        },
        # Chino Mandarín
        "chino": {
            "zm_yunjian": "Chino Masculino Firme",
            "zm_yunxi": "Chino Masculino Calmo",
            "zm_yunxia": "Chino Masculino Enérgico",
            "zm_yunyang": "Chino Masculino Noticioso",
            "zf_xiaobei": "Chino Femenino Expresivo",
            "zf_xiaoni": "Chino Femenino",
            "zf_xiaoxiao": "Chino Femenino Narrativo",
            "zf_xiaoyi": "Chino Femenino Claro",
        },
    }

    def __init__(self, storage_engine, proyecto_id: str):
        self.storage = storage_engine
        self.proyecto_id = proyecto_id

        self.audios_dir = INPUT_DIR / proyecto_id / "audios"
        self.audios_dir.mkdir(parents=True, exist_ok=True)

        self.kokoro_script_path = Path("C:/ia-video/Kokoro/generador_kokoro.py")
        self.python_ejecutable = Path(r"C:\Users\SEGA\miniconda3\envs\kokoro_env\python.exe")

    def _preprocesar_texto(self, texto: str) -> str:
        # 1. Normalizar espacios
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        # 2. Normalizar comillas y caracteres conflictivos
        texto = texto.replace('"', '').replace("'", '').replace('«', '').replace('»', '')
        
        # 3. Evitar repeticiones descontroladas de caracteres
        texto = re.sub(r'([a-zA-ZáéíóúÁÉÍÓÚñÑ])\1{2,}', r'\1\1', texto)
        
        # 4. Asegurar puntuación suave
        texto = texto.replace('...', ', ')
        
        return texto.strip()

    def _obtener_duracion_wav(self, ruta_wav: Path) -> float:
        with wave.open(str(ruta_wav), 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return round(frames / float(rate), 2)

    def _ejecutar_kokoro_cli(self, texto: str, voz: str, ruta_salida: Path) -> bool:
        cmd = [
            str(self.python_ejecutable),
            str(self.kokoro_script_path),
            "--texto", texto,
            "--voz", voz,
            "--salida", str(ruta_salida)
        ]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            print(f"      [Subproceso Kokoro] Generando audio con voz/mezcla '{voz}'...")
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"[KOKORO CLI ERROR] Fallo al ejecutar el script:\n{e.stderr}\n{e.stdout}")
            return False
        except FileNotFoundError as e:
            print(f"[KOKORO CLI ERROR] No se encontró el ejecutable o script: {e}")
            return False

    def procesar_escena(self, escena_id: str) -> tuple[str, float]:
        self.audios_dir.mkdir(parents=True, exist_ok=True)
        config = self.storage.cargar_config(self.proyecto_id)

        escena = next((e for e in config.get("escenas", []) if e["id"] == escena_id), None)
        if not escena:
            raise ValueError(f"Escena '{escena_id}' no encontrada en la configuración.")

        dialogo = escena.get("dialogo", "").strip()

        if not dialogo:
            for e in config["escenas"]:
                if e["id"] == escena_id:
                    e["duracion_audio"] = 0.0
                    break
            self.storage.guardar_config(self.proyecto_id, config)
            print(f"[TTS] Escena {escena_id} sin diálogo. Omitida (0.0s).")
            return None, 0.0

        # Resolver voz directamente desde personajes en guion/config sin traducciones
        personaje_id = escena.get("personaje_id")
        personajes = config.get("personajes", {})

        if personaje_id and personaje_id in personajes:
            p_data = personajes[personaje_id]
            voz_final = p_data.get("voz_tts", p_data.get("voz", self.VOZ_FALLBACK_HOMBRE)).strip()
        elif len(personajes) == 1:
            p_data = next(iter(personajes.values()))
            voz_final = p_data.get("voz_tts", p_data.get("voz", self.VOZ_FALLBACK_HOMBRE)).strip()
        else:
            voz_final = config.get("voz_global", self.VOZ_FALLBACK_HOMBRE).strip()

        if not voz_final:
            voz_final = self.VOZ_FALLBACK_HOMBRE

        dialogo_optimizado = self._preprocesar_texto(dialogo)
        ruta_salida = self.audios_dir / f"{escena_id}.wav"

        if ruta_salida.exists():
            ruta_salida.unlink()

        exito = self._ejecutar_kokoro_cli(dialogo_optimizado, voz_final, ruta_salida)

        if not exito or not ruta_salida.exists():
            raise RuntimeError(f"Fallo crítico generando audio para {escena_id} con Kokoro.")

        duracion = self._obtener_duracion_wav(ruta_salida)

        for e in config["escenas"]:
            if e["id"] == escena_id:
                e["duracion_audio"] = duracion
                break
        self.storage.guardar_config(self.proyecto_id, config)

        print(f"[TTS] Archivo generado: {ruta_salida.name} ({duracion}s) [Voz: {voz_final}]")
        return str(ruta_salida.name), duracion