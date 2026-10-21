import shutil
import time
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR
from core.storage_engine import StorageEngine
from core.comfy_client import ComfyAPIClient
from modules.enhancer_engine import EnhancerEngine


class VideoEngine:
    """
    Fase 5: Lip-Sync Facial HD (LivePortrait) + Masterización Automática (FFmpeg Enhancer).
    Garantiza un único archivo master final por escena ({escena_id}_enhanced.mp4)
    sin duplicados ni archivos temporales residuales.
    """

    def __init__(self, storage_engine: StorageEngine, api_client: ComfyAPIClient, proyecto_id: str):
        self.storage = storage_engine
        self.api = api_client
        self.proyecto_id = proyecto_id
        self.enhancer = EnhancerEngine(proyecto_id)

        self.comfy_input_ref_dir = INPUT_DIR / proyecto_id / "ref_images"
        self.comfy_input_driving_dir = INPUT_DIR / proyecto_id / "driving"
        self.sadtalker_output_dir = OUTPUT_DIR / proyecto_id / "sadtalker_temp"
        self.renders_output_dir = OUTPUT_DIR / proyecto_id / "renders"

        self.comfy_input_ref_dir.mkdir(parents=True, exist_ok=True)
        self.comfy_input_driving_dir.mkdir(parents=True, exist_ok=True)
        self.renders_output_dir.mkdir(parents=True, exist_ok=True)

    def _limpiar_archivos_escena(self, escena_id: str, excluir: Path = None):
        """Elimina todos los archivos temporales, intermedios y previos de la escena."""
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

    def _resolver_imagen_personaje(self, escena_id: str, nombre_sugerido: str = "") -> Path:
        if nombre_sugerido:
            ruta_directa = self.comfy_input_ref_dir / nombre_sugerido
            if ruta_directa.exists():
                return ruta_directa

        candidatos_in = list(self.comfy_input_ref_dir.glob(f"{escena_id}_personaje*.png"))
        if candidatos_in:
            return candidatos_in[0]

        ref_out = OUTPUT_DIR / self.proyecto_id / "ref_images"
        if ref_out.exists():
            candidatos_out = list(ref_out.glob(f"{escena_id}_personaje*.png"))
            if candidatos_out:
                destino = self.comfy_input_ref_dir / candidatos_out[0].name
                shutil.copy2(candidatos_out[0], destino)
                return destino

        raise FileNotFoundError(f"No se encontró imagen HD para '{escena_id}'.")

    def _resolver_driving_video(self, escena_id: str, nombre_sugerido: str = "") -> Path:
        archivo_driving = None
        if nombre_sugerido:
            ruta_directa = self.sadtalker_output_dir / nombre_sugerido
            if ruta_directa.exists():
                archivo_driving = ruta_directa

        if not archivo_driving or not archivo_driving.exists():
            candidatos = list(self.sadtalker_output_dir.glob(f"{escena_id}*.mp4"))
            if candidatos:
                archivo_driving = candidatos[0]
            else:
                raise FileNotFoundError(f"No se encontró video driving para '{escena_id}'.")

        destino_input = self.comfy_input_driving_dir / f"{escena_id}_driving.mp4"
        shutil.copy2(archivo_driving, destino_input)
        return destino_input

    def renderizar_lipsync(self, escena_id: str, nombre_imagen: str = "", nombre_driving_video: str = "") -> tuple[bool, str]:
        # 1. Limpieza preventiva total de cualquier render previo de esta escena
        self._limpiar_archivos_escena(escena_id)

        source_img = self._resolver_imagen_personaje(escena_id, nombre_imagen)
        driving_vid = self._resolver_driving_video(escena_id, nombre_driving_video)

        workflow = self.storage.obtener_plantilla(self.proyecto_id, "wf_liveportrait_lipsync.json")

        ruta_relativa_imagen = f"projects/{self.proyecto_id}/ref_images/{source_img.name}"
        ruta_relativa_driving = f"projects/{self.proyecto_id}/driving/{driving_vid.name}"
        prefijo_salida = f"projects/{self.proyecto_id}/renders/{escena_id}_liveportrait"

        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            if class_type == "LoadImage":
                inputs["image"] = ruta_relativa_imagen
            elif class_type == "VHS_LoadVideo":
                inputs["video"] = ruta_relativa_driving
            elif class_type == "VHS_VideoCombine":
                inputs["filename_prefix"] = prefijo_salida

        print(f"[VideoEngine] Renderizando LivePortrait HD para {escena_id}...")
        prompt_id, outputs = self.api.ejecutar_workflow(workflow, timeout=600)

        video_raw_temp = self.renders_output_dir / f"{escena_id}_final.mp4"
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
            candidatos = list(self.renders_output_dir.glob(f"{escena_id}_liveportrait*.mp4"))
            if not candidatos:
                candidatos = [f for f in self.renders_output_dir.glob("*.mp4") if escena_id in f.name and "enhanced" not in f.name]
            if candidatos:
                video_encontrado = max(candidatos, key=lambda p: p.stat().st_mtime)

        if not video_encontrado or not video_encontrado.exists():
            raise FileNotFoundError(f"ComfyUI completó pero no se halló el video para {escena_id}.")

        # Renombrar salida de ComfyUI como archivo intermedio base
        if video_raw_temp.exists():
            video_raw_temp.unlink()
        shutil.move(str(video_encontrado), str(video_raw_temp))

        # 2. Ejecución de la mejora de calidad (FFmpeg Enhancer)
        video_master = self.enhancer.mejorar_escena(escena_id, forzar=True)

        # 3. Eliminar el archivo intermedio sin mejorar para no duplicar espacio
        if video_raw_temp.exists() and video_master.exists() and video_raw_temp.resolve() != video_master.resolve():
            try:
                video_raw_temp.unlink()
            except Exception:
                pass

        # 4. Limpieza final de seguridad: asegurar que solo quede el master enhanced
        self._limpiar_archivos_escena(escena_id, excluir=video_master)

        print(f"[VideoEngine] [ÉXITO] Video Master HD único listo: {video_master.name}")
        return True, prompt_id