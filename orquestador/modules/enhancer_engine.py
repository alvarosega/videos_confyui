import subprocess
import shutil
from pathlib import Path
from config import OUTPUT_DIR


class EnhancerEngine:
    """
    Fase 6: Masterización y realce cinemático de video mediante FFmpeg.
    Aplica enfoque quirúrgico de alta frecuencia, recuperación de negros puros,
    micrograno analógico anti-banding y recodificación en H.264 CRF 14.
    """

    def __init__(self, proyecto_id: str):
        self.proyecto_id = proyecto_id
        self.renders_dir = OUTPUT_DIR / proyecto_id / "renders"
        self.renders_dir.mkdir(parents=True, exist_ok=True)

    def _verificar_ffmpeg(self) -> str:
        """Comprueba la disponibilidad del ejecutable de FFmpeg en el sistema."""
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            return ffmpeg_bin

        rutas_fallback = [
            Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Users\SEGA\anaconda3\Library\bin\ffmpeg.exe"),
            Path(r"C:\Users\SEGA\miniconda3\Library\bin\ffmpeg.exe"),
            Path(r"C:\Users\SEGA\miniconda3\envs\sadtalker\Library\bin\ffmpeg.exe"),
            Path(r"C:\Users\SEGA\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe"),
        ]

        for ruta in rutas_fallback:
            if ruta.exists():
                return str(ruta)

        raise FileNotFoundError("FFmpeg no está disponible en el PATH ni en las rutas del sistema.")

    def mejorar_escena(self, escena_id: str, forzar: bool = False) -> Path:
        """
        Toma el archivo {escena_id}_final.mp4 generado por LivePortrait o B-Roll y
        produce {escena_id}_enhanced.mp4 con calidad de masterizado HD.
        """
        video_input = self.renders_dir / f"{escena_id}_final.mp4"
        video_output = self.renders_dir / f"{escena_id}_enhanced.mp4"

        if not video_input.exists():
            raise FileNotFoundError(f"Video base no encontrado para mejorar: {video_input}")

        if video_output.exists() and not forzar:
            print(f"[EnhancerEngine] {video_output.name} ya existe. Omitiendo proceso.")
            return video_output

        ffmpeg_cmd = self._verificar_ffmpeg()

        # Cadena de filtros quirúrgicos: Enfoque Luma + Profundidad Negros + Micrograno
        filter_chain = (
            "unsharp=lx=5:ly=5:la=0.85:cx=3:cy=3:ca=0.0,"
            "eq=contrast=1.06:brightness=-0.015:saturation=0.96,"
            "noise=alls=3:allf=t+u"
        )

        tmp_output = self.renders_dir / f"tmp_enh_{escena_id}.mp4"
        if tmp_output.exists():
            tmp_output.unlink()

        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i", str(video_input),
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "14",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(tmp_output)
        ]

        print(f"\n[EnhancerEngine] Mejorando calidad para '{escena_id}' (CRF 14 + Unsharp + Dithering)...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            if tmp_output.exists():
                tmp_output.unlink()
            raise RuntimeError(f"Fallo en FFmpeg Enhancer:\n{result.stderr}")

        if video_output.exists():
            video_output.unlink()

        shutil.move(str(tmp_output), str(video_output))
        print(f"[EnhancerEngine] [ÉXITO] Video Master HD listo: {video_output.name}")
        return video_output

    def procesar_todas_las_escenas(self) -> list[Path]:
        """Procesa en lote todos los renders finales existentes en el proyecto."""
        archivos_finales = sorted(list(self.renders_dir.glob("*_final.mp4")))
        if not archivos_finales:
            print(f"[EnhancerEngine] No se encontraron archivos *_final.mp4 en {self.renders_dir}")
            return []

        mejorados = []
        for vid in archivos_finales:
            escena_id = vid.stem.replace("_final", "")
            out = self.mejorar_escena(escena_id, forzar=True)
            mejorados.append(out)

        return mejorados
