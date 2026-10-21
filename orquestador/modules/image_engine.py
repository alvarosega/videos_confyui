import random
import shutil
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR
from core.storage_engine import StorageEngine
from core.comfy_client import ComfyAPIClient


class ImageEngine:
    def __init__(self, storage_engine: StorageEngine, api_client: ComfyAPIClient, proyecto_id: str):
        self.storage = storage_engine
        self.api_client = api_client
        self.proyecto_id = proyecto_id
        
        self.comfy_input_dir = INPUT_DIR / proyecto_id / "ref_images"
        self.comfy_output_dir = OUTPUT_DIR / proyecto_id / "ref_images"
        self.poses_base_dir = INPUT_DIR.parent / "poses_base"
        
        self._garantizar_directorios()

    def _garantizar_directorios(self):
        self.comfy_input_dir.mkdir(parents=True, exist_ok=True)
        self.comfy_output_dir.mkdir(parents=True, exist_ok=True)
        self.poses_base_dir.mkdir(parents=True, exist_ok=True)

    def _limpiar_archivos_previos(self, patron_busqueda: str):
        if self.comfy_output_dir.exists():
            for archivo in self.comfy_output_dir.glob(patron_busqueda):
                try:
                    archivo.unlink()
                except Exception:
                    pass

    def _obtener_pose_aleatoria(self) -> str:
        extensiones = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
        poses = []
        for ext in extensiones:
            poses.extend(list(self.poses_base_dir.glob(ext)))
        
        if not poses:
            raise FileNotFoundError(
                f"No se encontraron imágenes de pose en {self.poses_base_dir}."
            )
        
        pose_elegida = random.choice(poses)
        return f"poses_base/{pose_elegida.name}"

    def _resolver_ruta_salida(self, info_img: dict) -> Path:
        nombre_generado = info_img.get("filename", "")
        subcarpeta = info_img.get("subfolder", "")
        if subcarpeta:
            ruta = OUTPUT_DIR.parent / subcarpeta / nombre_generado
            if ruta.exists(): return ruta
        ruta_directa = self.comfy_output_dir / nombre_generado
        if ruta_directa.exists(): return ruta_directa
        ruta_raiz = OUTPUT_DIR.parent / nombre_generado
        if ruta_raiz.exists(): return ruta_raiz
        raise FileNotFoundError(f"Archivo no hallado en disco: {nombre_generado}")

    def asegurar_imagen_maestra_personaje(self, personaje_id: str, p_data: dict, forzar_regeneracion: bool = False) -> Path:
        self._garantizar_directorios()
        master_input_path = self.comfy_input_dir / f"master_{personaje_id}.png"
        if not forzar_regeneracion and master_input_path.exists():
            return master_input_path

        self._limpiar_archivos_previos(f"master_{personaje_id}_*.png")
        wf = self.storage.obtener_plantilla(self.proyecto_id, "wf_personaje_master.json")

        guardrail_pos_master = "(solo:1.4), (1man:1.4), (strictly frontal face:1.5), (perfectly centered:1.4), (head and full forehead visible:1.4), (chest-up composition:1.4), crisp lip contour"
        guardrail_neg_master = "naked, shirtless, bare chest, topless, (multiple people:1.6), (2people:1.6), (group:1.6), (crowd:1.6), (profile view:1.5), (side view:1.5), (cropped head:1.5)"
        config = self.storage.cargar_config(self.proyecto_id)

        prompt_pos = f"{guardrail_pos_master}, {p_data.get('prompt_positivo_base', '')}, {config.get('estilo_global', '')}"
        prompt_neg = f"{guardrail_neg_master}, {p_data.get('prompt_negativo_base', '')}, {config.get('prompt_negativo_global', '')}"

        wf["3"]["inputs"]["seed"] = random.randint(1, 2**31 - 1)
        wf["6"]["inputs"]["text"] = prompt_pos
        wf["7"]["inputs"]["text"] = prompt_neg
        wf["9"]["inputs"]["filename_prefix"] = f"projects/{self.proyecto_id}/ref_images/master_{personaje_id}"

        print(f"[ImageEngine] Generando Imagen Maestra: {personaje_id}...")
        _, outputs = self.api_client.ejecutar_workflow(wf)
        ruta_generada = self._resolver_ruta_salida(outputs[0])
        shutil.copy2(ruta_generada, master_input_path)
        return master_input_path

    def renderizar_escena_personaje(self, escena_id: str) -> Path:
        self._garantizar_directorios()
        config = self.storage.cargar_config(self.proyecto_id)
        escena = next((e for e in config.get("escenas", []) if e["id"] == escena_id), None)
        p_data = config.get("personajes", {}).get(escena.get("personaje_id"), {})
        
        self.asegurar_imagen_maestra_personaje(escena["personaje_id"], p_data)
        self._limpiar_archivos_previos(f"{escena_id}_personaje_*.png")
        wf = self.storage.obtener_plantilla(self.proyecto_id, "wf_escena_personaje.json")

        estilo_global = config.get("estilo_global", "")
        negativo_global = config.get("prompt_negativo_global", "")

        # 1. ENTORNO Y CUERPO (Prioriza el entorno sin saturar los primeros 30 tokens)
        anclaje_aislamiento = "(solo:1.4), (1man:1.4), (strictly frontal view:1.4)"
        prompt_escena = f"{anclaje_aislamiento}, ({escena.get('accion_prompt', '')}:1.35), {estilo_global}"
        
        # 2. TRASPLANTE FACIAL (FaceDetailer)
        prompt_rostro = f"(solo:1.4), (strictly frontal face:1.5), crisp distinct lip contour, strictly closed neutral mouth, {p_data.get('prompt_positivo_base', '')}, {estilo_global}"
        
        # 3. NEGATIVO CON BLOQUEO DE FONDOS LISOS Y FANTASMAS
        bloqueo_fondo_liso = "(plain background:1.5), (solid background:1.5), (empty wall:1.5), (flat studio backdrop:1.5), (pitch black empty void:1.4), (featureless wall:1.4), (solid color:1.5)"
        bloqueo_multitudes = "(multiple people:1.6), (2people:1.6), (two men:1.6), (group:1.6), (duplicate:1.6), (statues:1.5), (mannequins:1.5)"
        bloqueo_recortes = "(cropped head:1.6), (cropped forehead:1.6), (cropped chin:1.6), (out of frame:1.5)"
        bloqueo_orientacion = "(back view:1.6), (turned away:1.6), (looking away:1.5), (side view:1.5)"
        anatomia_negativa = "(bad anatomy:1.6), (extra limbs:1.5), (mutated hands:1.5)"
        
        prompt_negativo = (
            f"{bloqueo_fondo_liso}, {bloqueo_multitudes}, {bloqueo_recortes}, {bloqueo_orientacion}, "
            f"{anatomia_negativa}, ({escena.get('prompt_negativo_escena', '')}:1.2), "
            f"{p_data.get('prompt_negativo_base', '')}, {negativo_global}"
        )

        semilla = random.randint(1, 2**31 - 1)
        wf["3"]["inputs"]["seed"] = semilla
        wf["15"]["inputs"]["seed"] = semilla
        wf["6"]["inputs"]["text"] = prompt_escena
        wf["16"]["inputs"]["text"] = prompt_rostro
        wf["7"]["inputs"]["text"] = prompt_negativo
        
        wf["9"]["inputs"]["filename_prefix"] = f"projects/{self.proyecto_id}/ref_images/{escena_id}_personaje"
        wf["10"]["inputs"]["image"] = f"projects/{self.proyecto_id}/ref_images/master_{escena['personaje_id']}.png"
        
        ruta_pose = self._obtener_pose_aleatoria()
        wf["17"]["inputs"]["image"] = ruta_pose

        print(f"[ImageEngine] Renderizando {escena_id} (Pose: {ruta_pose.split('/')[-1]})...")
        _, outputs = self.api_client.ejecutar_workflow(wf)
        
        ruta_generada = self._resolver_ruta_salida(outputs[0])
        return ruta_generada

    def renderizar_escena_broll(self, escena_id: str) -> Path:
        self._garantizar_directorios()
        config = self.storage.cargar_config(self.proyecto_id)
        escena = next((e for e in config.get("escenas", []) if e["id"] == escena_id), None)
        self._limpiar_archivos_previos(f"{escena_id}_b_roll_*.png")
        self._limpiar_archivos_previos(f"{escena_id}_broll_*.png")
        wf = self.storage.obtener_plantilla(self.proyecto_id, "wf_escena_broll.json")
        
        wf["5"]["inputs"]["width"] = 768
        wf["5"]["inputs"]["height"] = 1344

        pos = f"({escena.get('accion_prompt', '')}:1.3), {config.get('estilo_global', '')}"
        neg = f"({escena.get('prompt_negativo_escena', '')}:1.2), (people:1.5), faces, human, {config.get('prompt_negativo_global', '')}"

        wf["3"]["inputs"]["seed"] = random.randint(1, 2**31 - 1)
        wf["6"]["inputs"]["text"] = pos
        wf["7"]["inputs"]["text"] = neg
        wf["9"]["inputs"]["filename_prefix"] = f"projects/{self.proyecto_id}/ref_images/{escena_id}_b_roll"

        print(f"[ImageEngine] Renderizando B-Roll {escena_id}...")
        _, outputs = self.api_client.ejecutar_workflow(wf)
        return self._resolver_ruta_salida(outputs[0])