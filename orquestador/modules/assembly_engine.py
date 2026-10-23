import os
import shutil
import subprocess
from pathlib import Path
from config import OUTPUT_DIR, INPUT_DIR


class AssemblyEngine:
    """Módulo para el ensamblaje secuencial y masterizado final de la película."""

    def __init__(self, proyecto_id: str, storage_engine=None):
        self.proyecto_id = proyecto_id
        self.storage = storage_engine
        self.renders_dir = OUTPUT_DIR / proyecto_id / "renders"
        self.final_dir = OUTPUT_DIR / proyecto_id / "final"
        self.audios_dir = INPUT_DIR / proyecto_id / "audios"

        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)

    def _resolver_clips_ordenados(self) -> list[Path]:
        """
        Resuelve los clips en el orden exacto del guion narrativo,
        priorizando la versión masterizada (*_enhanced.mp4) sobre la cruda (*_final.mp4).
        """
        clips_ordenados = []

        if self.storage:
            try:
                config = self.storage.cargar_config(self.proyecto_id)
                escenas = config.get("escenas", [])
                for esc in escenas:
                    e_id = esc.get("id")
                    if not e_id:
                        continue
                    # 1. Prioridad: Versión mejorada por EnhancerEngine (LivePortrait HD)
                    clip_enh = self.renders_dir / f"{e_id}_enhanced.mp4"
                    # 2. Alternativa: Versión base (B-Roll o render crudo)
                    clip_fin = self.renders_dir / f"{e_id}_final.mp4"

                    if clip_enh.exists():
                        clips_ordenados.append(clip_enh)
                    elif clip_fin.exists():
                        clips_ordenados.append(clip_fin)
                    else:
                        print(f"[AssemblyEngine] Aviso: No se encontró render para escena '{e_id}'.")
            except Exception as e:
                print(f"[AssemblyEngine] Aviso al leer configuración de proyecto: {e}")

        # Fallback si no hay config o no se hallaron clips mediante el guion
        if not clips_ordenados:
            todos_candidatos = list(self.renders_dir.glob("*_enhanced.mp4")) + list(self.renders_dir.glob("*_final.mp4"))
            mapeo_escenas = {}
            for clip in todos_candidatos:
                prefijo = clip.stem.replace("_enhanced", "").replace("_final", "")
                if prefijo not in mapeo_escenas or "_enhanced" in clip.name:
                    mapeo_escenas[prefijo] = clip
            clips_ordenados = [mapeo_escenas[k] for k in sorted(mapeo_escenas.keys())]

        return clips_ordenados

    def ensamblar_pelicula(self, nombre_salida: str = "pelicula_final.mp4") -> Path:
        clips = self._resolver_clips_ordenados()
        if not clips:
            raise FileNotFoundError(
                f"No se encontraron clips de video válidos en {self.renders_dir} para ensamblar."
            )

        print(f"\n[AssemblyEngine] Ensamblando {len(clips)} escenas en orden narrativo:")
        for idx, c in enumerate(clips, 1):
            print(f"  {idx}. {c.name}")

        lista_txt = self.renders_dir / "lista_concat.txt"
        with open(lista_txt, "w", encoding="utf-8") as f:
            for c in clips:
                # Formato FFmpeg concat seguro con barras estándar
                f.write(f"file '{c.resolve().as_posix()}'\n")

        ruta_out = self.final_dir / nombre_salida

        # Intentar concatenación rápida sin recodificación (-c copy)
        comando_fast = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_txt),
            "-c", "copy",
            str(ruta_out)
        ]

        try:
            subprocess.run(comando_fast, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            print("[AssemblyEngine] Concat directo no compatible por variaciones de codec. Recodificando a H.264 homogéneo...")
            # Fallback seguro con recodificación si difieren codecs o timebases
            comando_reencode = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(lista_txt),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "16",
                "-c:a", "aac",
                "-b:a", "192k",
                str(ruta_out)
            ]
            subprocess.run(comando_reencode, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        if lista_txt.exists():
            lista_txt.unlink()

        print(f"[AssemblyEngine] [ÉXITO] Película masterizada exportada en: {ruta_out}")
        return ruta_out
