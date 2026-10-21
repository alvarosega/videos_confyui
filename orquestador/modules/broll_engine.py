import random
import shutil
import time
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR
from core.storage_engine import StorageEngine
from core.comfy_client import ComfyAPIClient


class BRollAnimationEngine:
    """Fase 4b: Animación cinematográfica optimizada de B-Roll con SVD y RIFE."""

    def __init__(self, storage_engine: StorageEngine, api_client: ComfyAPIClient, proyecto_id: str):
        self.storage = storage_engine
        self.api = api_client
        self.proyecto_id = proyecto_id

        self.comfy_input_ref_dir = INPUT_DIR / proyecto_id / "ref_images"
        self.comfy_output_ref_dir = OUTPUT_DIR / proyecto_id / "ref_images"
        self.renders_output_dir = OUTPUT_DIR / proyecto_id / "renders"

        self.comfy_input_ref_dir.mkdir(parents=True, exist_ok=True)
        self.renders_output_dir.mkdir(parents=True, exist_ok=True)

    def _limpiar_archivos_escena(self, escena_id: str, excluir: Path = None):
        """Elimina archivos residuales y versiones previas de la escena."""
        if not self.renders_output_dir.exists():
            return

        for archivo in self.renders_output_dir.glob(f"{escena_id}_*"):
            if excluir and archivo.resolve() == excluir.resolve():
                continue
            try:
                if archivo.is_file():
                    archivo.unlink()
            except Exception:
                pass

    def _resolver_imagen_broll(self, escena_id: str) -> Path:
        candidatos_in = list(self.comfy_input_ref_dir.glob(f"{escena_id}_b_roll*.png")) + \
                        list(self.comfy_input_ref_dir.glob(f"{escena_id}_broll*.png"))
        if candidatos_in:
            return candidatos_in[0]

        if self.comfy_output_ref_dir.exists():
            candidatos_out = list(self.comfy_output_ref_dir.glob(f"{escena_id}_b_roll*.png")) + \
                             list(self.comfy_output_ref_dir.glob(f"{escena_id}_broll*.png"))
            if candidatos_out:
                destino = self.comfy_input_ref_dir / candidatos_out[0].name
                shutil.copy2(candidatos_out[0], destino)
                return destino

        raise FileNotFoundError(
            f"No se encontró la imagen base B-Roll para '{escena_id}'. "
            f"Ejecute la Fase 3 (Renderizado de Imágenes) primero."
        )

    def animar_escena_broll(self, escena_id: str) -> Path:
        config = self.storage.cargar_config(self.proyecto_id)
        escena = next((e for e in config.get("escenas", []) if e["id"] == escena_id), None)
        if not escena or escena.get("tipo") != "b_roll":
            raise ValueError(f"Escena '{escena_id}' no es un B-Roll válido en la configuración.")

        # 1. Purga preventiva
        self._limpiar_archivos_escena(escena_id)

        img_path = self._resolver_imagen_broll(escena_id)
        workflow = self.storage.obtener_plantilla(self.proyecto_id, "wf_escena_broll_animation.json")

        ruta_relativa_imagen = f"projects/{self.proyecto_id}/ref_images/{img_path.name}"
        prefijo_salida = f"projects/{self.proyecto_id}/renders/{escena_id}_broll_animated"
        semilla = random.randint(1, 2**31 - 1)

        # Inyección dinámica
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            if class_type == "LoadImage":
                inputs["image"] = ruta_relativa_imagen
            elif class_type == "KSampler":
                inputs["seed"] = semilla
            elif class_type == "VHS_VideoCombine":
                inputs["filename_prefix"] = prefijo_salida

        print(f"[BRollEngine] Animando B-Roll para {escena_id} (14 frames SVD + RIFE 4x)...")
        prompt_id, outputs = self.api.ejecutar_workflow(workflow, timeout=300)

        video_final = self.renders_output_dir / f"{escena_id}_final.mp4"
        video_encontrado = None

        if outputs:
            info_vid = outputs[0]
            nombre_gen = info_vid.get("filename", "")
            subcarpeta = info_vid.get("subfolder", "")
            ruta_gen = (OUTPUT_DIR.parent / subcarpeta / nombre_gen) if subcarpeta else (OUTPUT_DIR / nombre_gen)
            if not ruta_gen.exists():
                ruta_gen = self.renders_output_dir / nombre_gen

            if ruta_gen.exists():
                video_encontrado = ruta_gen

        if not video_encontrado:
            time.sleep(1)
            candidatos = list(self.renders_output_dir.glob(f"{escena_id}_broll_animated*.mp4"))
            if not candidatos:
                candidatos = [f for f in self.renders_output_dir.glob("*.mp4") if escena_id in f.name and "final" not in f.name]

            if candidatos:
                video_encontrado = max(candidatos, key=lambda p: p.stat().st_mtime)

        if not video_encontrado or not video_encontrado.exists():
            raise FileNotFoundError(f"ComfyUI completó pero no se halló el video B-Roll generado para {escena_id}.")

        if video_final.exists():
            video_final.unlink()
        shutil.move(str(video_encontrado), str(video_final))

        # 2. Barrido posterior
        self._limpiar_archivos_escena(escena_id, excluir=video_final)

        print(f" -> Video B-Roll completado: {video_final.name}")
        return video_final