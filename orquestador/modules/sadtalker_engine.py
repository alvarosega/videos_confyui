import shutil
import subprocess
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR, BASE_DIR, COMFYUI_DIR


class SadTalkerEngine:
    """
    Fase 4: Generador de driving video con morfologÃ­a 1:1.
    Utiliza como source la imagen renderizada real del personaje en lugar de un avatar externo,
    garantizando coincidencia exacta de landmarks y anulando traslaciones espaciales con --still.
    """

    ARQUETIPOS_ESCENA = [
        {"pose_style": 0, "exp": 1.05, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.02, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.08, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.04, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.06, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.03, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.07, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.05, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.02, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.08, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.04, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.06, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.03, "yaw": 0, "pitch": 0, "roll": 0},
        {"pose_style": 0, "exp": 1.05, "yaw": 0, "pitch": 0, "roll": 0},
    ]

    def __init__(self, proyecto_id: str):
        self.proyecto_id = proyecto_id
        self.python_sadtalker = Path(r"C:\Users\SEGA\miniconda3\envs\sadtalker\python.exe")
        self.sadtalker_dir = BASE_DIR / "SadTalker"

        self.ref_base_dir = COMFYUI_DIR / "output" / "ref"
        self.project_input_dir = INPUT_DIR / proyecto_id
        self.input_ref_dir = self.project_input_dir / "ref_images"
        self.output_ref_dir = OUTPUT_DIR / proyecto_id / "ref_images"
        self.input_audio_dir = self.project_input_dir / "audios"
        self.output_dir = OUTPUT_DIR / proyecto_id / "sadtalker_temp"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._contador_escenas = 0

    def _resolver_arquetipo(self, escena_id: str) -> dict:
        try:
            num = int(''.join(filter(str.isdigit, escena_id)))
            idx = (num - 1) % len(self.ARQUETIPOS_ESCENA)
        except Exception:
            idx = self._contador_escenas % len(self.ARQUETIPOS_ESCENA)
            self._contador_escenas += 1
        return self.ARQUETIPOS_ESCENA[idx]

    def _resolver_imagen_fuente(self, escena_id: str, avatar_nombre: str) -> Path:
        """Prioriza la imagen real de la escena o el master para garantizar coincidencia morfomÃ©trica."""
        # 1. Imagen renderizada de la escena
        candidatos_escena = list(self.input_ref_dir.glob(f"{escena_id}_personaje*.png"))
        if not candidatos_escena:
            candidatos_escena = list(self.output_ref_dir.glob(f"{escena_id}_personaje*.png"))
        if candidatos_escena:
            return candidatos_escena[0]

        # 2. Imagen maestra del personaje
        candidatos_master = list(self.input_ref_dir.glob("master_*.png"))
        if not candidatos_master:
            candidatos_master = list(self.output_ref_dir.glob("master_*.png"))
        if candidatos_master:
            return candidatos_master[0]

        # 3. Fallback a avatar_nombre declarado
        if (self.input_ref_dir / avatar_nombre).exists():
            return self.input_ref_dir / avatar_nombre
        if (self.ref_base_dir / avatar_nombre).exists():
            return self.ref_base_dir / avatar_nombre

        raise FileNotFoundError(
            f"No se encontrÃ³ imagen base para '{escena_id}'. Renderice la Fase 3 primero."
        )

    def generar_video_borrador(
        self,
        escena_id: str,
        avatar_nombre: str,
        audio_nombre: str,
        expression_scale: float = None,
        pose_style: int = None
    ) -> Path:
        source_image = self._resolver_imagen_fuente(escena_id, avatar_nombre)
        driven_audio = self.input_audio_dir / audio_nombre
        target_video = self.output_dir / f"{escena_id}_driving.mp4"

        if not driven_audio.exists():
            raise FileNotFoundError(f"Audio no encontrado: {driven_audio}")

        arquetipo = self._resolver_arquetipo(escena_id)
        estilo_final = pose_style if pose_style is not None else arquetipo["pose_style"]
        exp_final = expression_scale if expression_scale is not None else arquetipo["exp"]
        yaw_deg = arquetipo["yaw"]
        pitch_deg = arquetipo["pitch"]
        roll_deg = arquetipo["roll"]

        if target_video.exists():
            target_video.unlink()

        escena_temp_dir = self.output_dir / f"tmp_{escena_id}"
        escena_temp_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.python_sadtalker),
            str(self.sadtalker_dir / "inference.py"),
            "--driven_audio", str(driven_audio),
            "--source_image", str(source_image),
            "--result_dir", str(escena_temp_dir),
            "--preprocess", "crop",
            "--size", "256",
            "--batch_size", "1",
            "--still",
            "--expression_scale", str(exp_final),
            "--pose_style", str(estilo_final),
            "--input_yaw", str(yaw_deg),
            "--input_pitch", str(pitch_deg),
            "--input_roll", str(roll_deg)
        ]

        print(
            f"\n[SadTalker CLI] {escena_id} -> Source: {source_image.name} | "
            f"Exp: {exp_final} | Lock Spatial: [0Â°, 0Â°, 0Â°]"
        )

        result = subprocess.run(
            cmd,
            cwd=str(self.sadtalker_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            shutil.rmtree(escena_temp_dir, ignore_errors=True)
            raise RuntimeError(f"Fallo en SadTalker CLI:\n{result.stderr}")

        candidatos = list(escena_temp_dir.glob("*.mp4"))
        if not candidatos:
            shutil.rmtree(escena_temp_dir, ignore_errors=True)
            raise FileNotFoundError(f"SadTalker no produjo salida para {escena_id}.")

        shutil.move(str(candidatos[0]), str(target_video))
        shutil.rmtree(escena_temp_dir, ignore_errors=True)

        print(f"[SadTalker CLI] [Ã‰XITO] Video driving morfomÃ©trico listo: {target_video.name}")
        return target_video
