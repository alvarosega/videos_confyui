import json
import os
import sys
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path


class StorageEngine:
    """Maneja el almacenamiento aislado por proyecto y la administración de presets."""

    ESTILOS_PRESETS = {
        "dark_concept": {
            "nombre": "Dark Concept Art (Unreal Engine 5 / Moody)",
            "estilo_global": "dark concept art, cinematic moody lighting, deep shadows, dramatic chiaroscuro, stylized digital painting, unreal engine 5 render, high contrast, atmospheric depth, muted color palette, highly detailed, 8k resolution, masterpiece",
            "prompt_negativo_global": "multiple people, two people, two men, duplicate, clone, twins, extra body, background person, extra head, photorealistic, camera skin pores, raw photograph, bright saturated colors, smooth plastic skin, low quality, deformed, bad anatomy, bad hands, extra limbs, distorted face, bad framing, blur, cropped head, out of frame head, cut off face, zoomed in close-up, top of head cut off, body out of frame, plain background, grey background, studio background, empty room, minimalist wall"
        },
        "photorealistic": {
            "nombre": "Fotorrealista (35mm Hasselblad)",
            "estilo_global": "raw photo, realistic skin pores, detailed skin texture, cinematic lighting, 35mm film photograph, shot on Hasselblad, shallow depth of field, 8k uhd, masterpiece",
            "prompt_negativo_global": "cartoon, 3d render, illustration, smooth plastic skin, deformed, bad anatomy, bad hands, extra limbs, distorted face, low quality, blur, cropped head, out of frame head, cut off face, zoomed in close-up, top of head cut off, body out of frame, plain background, grey background, studio background, empty room"
        }
    }

    def __init__(self):
        self.script_dir = Path(__file__).resolve().parent
        self.presets_dir = self.script_dir / "presets"

        if (self.script_dir.parent / "ComfyUI").exists():
            self.comfy_dir = self.script_dir.parent / "ComfyUI"
        elif (self.script_dir / "ComfyUI").exists():
            self.comfy_dir = self.script_dir / "ComfyUI"
        else:
            self.comfy_dir = self.script_dir.parent / "ComfyUI"

        self.output_dir = self.comfy_dir / "output" / "projects"
        self.input_dir = self.comfy_dir / "input" / "projects"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        self._asegurar_presets_locales()

    def _asegurar_presets_locales(self):
        """Genera las plantillas de LTX-Video I2V si no existen físicamente."""
        dark_dir = self.presets_dir / "dark_concept"
        dark_dir.mkdir(parents=True, exist_ok=True)

        wf_a = dark_dir / "workflow_a_template.json"
        wf_b = dark_dir / "workflow_b_template.json"

        if not wf_a.exists():
            data_a = {
                "1": {"inputs": {"ckpt_name": "DreamShaper_v8.safetensors"}, "class_type": "CheckpointLoaderSimple"},
                "2": {"inputs": {"text": "", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
                "3": {"inputs": {"text": "", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
                "4": {"inputs": {"width": 512, "height": 512, "batch_size": 4}, "class_type": "EmptyLatentImage"},
                "5": {"inputs": {"seed": 0, "steps": 25, "cfg": 7.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}, "class_type": "KSampler"},
                "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
                "7": {"inputs": {"filename_prefix": "", "images": ["6", 0]}, "class_type": "SaveImage"}
            }
            with open(wf_a, "w", encoding="utf-8") as f:
                json.dump(data_a, f, indent=2)

        if not wf_b.exists():
            data_b = {
                "1": {"inputs": {"unet_name": "ltx-video-2b-v0.9.1.safetensors", "weight_dtype": "fp8_e4m3fn"}, "class_type": "UNETLoader"},
                "2_clip": {"inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "t5xxl", "device": "default"}, "class_type": "CLIPLoader"},
                "3_vae": {"inputs": {"vae_name": "ltx-video-vae.safetensors"}, "class_type": "VAELoader"},
                "2": {"inputs": {"text": "", "clip": ["2_clip", 0]}, "class_type": "CLIPTextEncode"},
                "3": {"inputs": {"text": "", "clip": ["2_clip", 0]}, "class_type": "CLIPTextEncode"},
                "32": {"inputs": {"image": ""}, "class_type": "LoadImage"},
                "4": {"inputs": {"vae": ["3_vae", 0], "image": ["32", 0], "positive": ["2", 0], "negative": ["3", 0], "width": 512, "height": 768, "length": 33, "batch_size": 1}, "class_type": "LTXVImgToVideo"},
                "7": {"inputs": {"model": ["1", 0]}, "class_type": "ModelSamplingLTXV"},
                "5": {"inputs": {"seed": 0, "steps": 20, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["7", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["4", 2]}, "class_type": "KSampler"},
                "6": {"inputs": {"samples": ["5", 0], "vae": ["3_vae", 0]}, "class_type": "VAEDecode"},
                "28": {"inputs": {"frame_rate": 24, "loop_count": 0, "filename_prefix": "", "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 19, "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True, "images": ["6", 0]}, "class_type": "VHS_VideoCombine"}
            }
            with open(wf_b, "w", encoding="utf-8") as f:
                json.dump(data_b, f, indent=2)

    def listar_proyectos(self):
        return [
            d.name
            for d in self.output_dir.iterdir()
            if d.is_dir() and (d / "project_config.json").exists()
        ]

    def crear_proyecto(self, nombre_id, preset_key, estilo_global, prompt_negativo_global):
        proj_dir = self.output_dir / nombre_id
        if proj_dir.exists():
            raise FileExistsError(f"El proyecto '{nombre_id}' ya existe en {proj_dir}.")

        (proj_dir / "01_assets" / "personajes").mkdir(parents=True, exist_ok=True)
        (proj_dir / "02_guion").mkdir(parents=True, exist_ok=True)
        (proj_dir / "03_renders").mkdir(parents=True, exist_ok=True)
        
        proj_templates_dir = proj_dir / "templates"
        proj_templates_dir.mkdir(parents=True, exist_ok=True)

        preset_src_dir = self.presets_dir / preset_key
        if not preset_src_dir.exists():
            preset_src_dir = self.presets_dir / "dark_concept"

        shutil.copy2(preset_src_dir / "workflow_a_template.json", proj_templates_dir / "workflow_a_template.json")
        shutil.copy2(preset_src_dir / "workflow_b_template.json", proj_templates_dir / "workflow_b_template.json")

        config = {
            "id_proyecto": nombre_id,
            "preset_usado": preset_key,
            "estilo_global": estilo_global,
            "prompt_negativo_global": prompt_negativo_global,
            "resolucion": "512x768",
            "personajes": {},
            "escenas": [],
        }

        self.guardar_config(nombre_id, config)
        return config

    def cargar_config(self, nombre_id):
        config_path = self.output_dir / nombre_id / "project_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"No se encontró 'project_config.json' para '{nombre_id}'.")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def guardar_config(self, nombre_id, config):
        config_path = self.output_dir / nombre_id / "project_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def obtener_plantilla_proyecto(self, nombre_id, nombre_plantilla):
        ruta_template = self.output_dir / nombre_id / "templates" / nombre_plantilla
        if not ruta_template.exists():
            raise FileNotFoundError(f"Plantilla no encontrada en proyecto '{nombre_id}': {ruta_template}")
        with open(ruta_template, "r", encoding="utf-8") as f:
            return json.load(f)

    def crear_carpeta_personaje(self, nombre_id, personaje_id):
        char_dir = self.output_dir / nombre_id / "01_assets" / "personajes" / personaje_id / "ref_images"
        char_dir.mkdir(parents=True, exist_ok=True)
        return char_dir

    def obtener_imagenes_referencia(self, nombre_id, personaje_id):
        char_dir = self.output_dir / nombre_id / "01_assets" / "personajes" / personaje_id / "ref_images"
        if not char_dir.exists():
            return []
        extensiones = [".png", ".jpg", ".jpeg", ".webp"]
        return [f for f in char_dir.iterdir() if f.is_file() and f.suffix.lower() in extensiones]

    def preparar_todas_referencias_para_input(self, nombre_id, personaje_id):
        imagenes = self.obtener_imagenes_referencia(nombre_id, personaje_id)
        if not imagenes:
            return []

        target_dir = self.input_dir / nombre_id / personaje_id
        target_dir.mkdir(parents=True, exist_ok=True)

        rutas_input = []
        for img in imagenes:
            target_file = target_dir / img.name
            shutil.copy2(img, target_file)
            rutas_input.append(f"projects/{nombre_id}/{personaje_id}/{img.name}")

        return rutas_input


class ComfyAPIClient:
    """Cliente HTTP para interactuar con la API local de ComfyUI."""

    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address

    def enviar_prompt(self, workflow_dict):
        url = f"http://{self.server_address}/prompt"
        payload = json.dumps({"prompt": workflow_dict}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                return True, res.get("prompt_id")
        except urllib.error.URLError as e:
            return False, str(e)


class PromptBuilder:
    """Concatena estrictamente los niveles de prompts sin inyectar restricciones fijas."""

    @staticmethod
    def construir_prompt_positivo(estilo_global, prompt_base_personaje, accion_escena=""):
        partes = [estilo_global, prompt_base_personaje, accion_escena]
        return ", ".join([p.strip().strip(",") for p in partes if p.strip()])

    @staticmethod
    def construir_prompt_negativo(prompt_negativo_global, prompt_negativo_base="", extra_negativo=""):
        partes = [prompt_negativo_global, prompt_negativo_base, extra_negativo]
        return ", ".join([p.strip().strip(",") for p in partes if p.strip()])


class WorkflowOrchestrator:
    """Inyecta parámetros en las plantillas aisladas del proyecto."""

    def __init__(self, storage_engine):
        self.storage = storage_engine

    def construir_workflow_a(self, proyecto_id, prompt_pos, prompt_neg, target_prefix):
        graph = self.storage.obtener_plantilla_proyecto(proyecto_id, "workflow_a_template.json")

        graph["2"]["inputs"]["text"] = prompt_pos
        graph["3"]["inputs"]["text"] = prompt_neg
        graph["5"]["inputs"]["seed"] = int(time.time())
        graph["7"]["inputs"]["filename_prefix"] = target_prefix

        return graph

    def construir_workflow_b(self, proyecto_id, prompt_pos, prompt_neg, rutas_imagenes_input, target_prefix):
        """Inyecta parámetros para LTX-Video I2V."""
        graph = self.storage.obtener_plantilla_proyecto(proyecto_id, "workflow_b_template.json")

        graph["2"]["inputs"]["text"] = prompt_pos
        graph["3"]["inputs"]["text"] = prompt_neg
        graph["5"]["inputs"]["seed"] = int(time.time())
        graph["28"]["inputs"]["filename_prefix"] = target_prefix

        if rutas_imagenes_input:
            graph["32"]["inputs"]["image"] = rutas_imagenes_input[0]

        return graph


class CLIInterface:
    """Interfaz por línea de comandos."""

    def __init__(self):
        self.storage = StorageEngine()
        self.api_client = ComfyAPIClient()
        self.orchestrator = WorkflowOrchestrator(self.storage)
        self.proyecto_activo = None
        self.config_activa = None

    def iniciar(self):
        while True:
            print("\n" + "=" * 50)
            print(" GESTOR DE PROYECTOS COMFYUI - CLI")
            print("=" * 50)
            if self.proyecto_activo:
                print(f"Proyecto actual: [{self.proyecto_activo}]")
                print(f"Preset activo: [{self.config_activa.get('preset_usado', 'personalizado')}]")
                print(f"Ruta ComfyUI: [{self.storage.comfy_dir}]")
                print("1. Gestión de Personajes")
                print("2. Gestión de Escenas y Guión")
                print("3. Generar Imágenes de Referencia (Workflow A - API)")
                print("4. Renderizar Video de Escena (Workflow B - API)")
                print("5. Ver / Configurar Estilo Global y Prompt Negativo")
                print("6. Diagnóstico del Proyecto")
                print("7. Cambiar / Cerrar Proyecto Activo")
                print("8. Salir")
            else:
                print("1. Crear Nuevo Proyecto")
                print("2. Cargar Proyecto Existente")
                print("3. Salir")

            opcion = input("\nSeleccione una opción: ").strip()

            if not self.proyecto_activo:
                if opcion == "1":
                    self.menu_crear_proyecto()
                elif opcion == "2":
                    self.menu_cargar_proyecto()
                elif opcion == "3":
                    sys.exit(0)
                else:
                    print("[ERROR] Opción inválida.")
            else:
                if opcion == "1":
                    self.menu_gestion_personajes()
                elif opcion == "2":
                    self.menu_gestion_escenas()
                elif opcion == "3":
                    self.menu_ejecutar_workflow_a()
                elif opcion == "4":
                    self.menu_ejecutar_workflow_b()
                elif opcion == "5":
                    self.menu_configurar_estilos_y_prompts()
                elif opcion == "6":
                    self.menu_diagnostico()
                elif opcion == "7":
                    self.proyecto_activo = None
                    self.config_activa = None
                elif opcion == "8":
                    sys.exit(0)
                else:
                    print("[ERROR] Opción inválida.")

    def menu_crear_proyecto(self):
        nombre = input("ID/Nombre del proyecto (ej: herencia_dark): ").strip()
        if not nombre:
            print("[ERROR] El nombre no puede estar vacío.")
            return

        print("\n--- SELECCIÓN DE PRESET DE ESTILO ---")
        presets = self.storage.ESTILOS_PRESETS
        keys = list(presets.keys())
        for idx, k in enumerate(keys, 1):
            print(f"{idx}. {presets[k]['nombre']}")
        print(f"{len(keys) + 1}. Personalizado")

        p_sel = input("Seleccione el preset base: ").strip()
        if p_sel.isdigit() and 1 <= int(p_sel) <= len(keys):
            preset_key = keys[int(p_sel) - 1]
            preset_data = presets[preset_key]
            estilo = preset_data["estilo_global"]
            prompt_neg_global = preset_data["prompt_negativo_global"]
        else:
            preset_key = "custom"
            estilo = input("Ingrese el Estilo Global (Positivo) personalizado: ").strip()
            prompt_neg_global = input("Ingrese el Prompt Negativo Global personalizado: ").strip()

        try:
            self.config_activa = self.storage.crear_proyecto(nombre, preset_key, estilo, prompt_neg_global)
            self.proyecto_activo = nombre
            print(f"\n[OK] Proyecto '{nombre}' creado con éxito en {self.storage.output_dir / nombre}.")
            print(f"[OK] Plantillas JSON aisladas creadas en {self.storage.output_dir / nombre / 'templates'}.")
        except Exception as e:
            print(f"[ERROR] {e}")

    def menu_cargar_proyecto(self):
        proyectos = self.storage.listar_proyectos()
        if not proyectos:
            print(f"[INFO] No hay proyectos guardados en {self.storage.output_dir}.")
            return

        print("\nProyectos disponibles:")
        for idx, p in enumerate(proyectos, 1):
            print(f"{idx}. {p}")

        sel = input("Seleccione el número del proyecto: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(proyectos):
            nombre = proyectos[int(sel) - 1]
            self.config_activa = self.storage.cargar_config(nombre)
            self.proyecto_activo = nombre
            print(f"[OK] Proyecto '{nombre}' cargado.")
        else:
            print("[ERROR] Selección fuera de rango.")

    def menu_configurar_estilos_y_prompts(self):
        print("\n" + "=" * 40)
        print(" CONFIGURACIÓN GLOBAL DE PROMPTS")
        print("=" * 40)
        print("\n[1] Estilo Global (Positivo):")
        print(f"    {self.config_activa['estilo_global']}")
        print("\n[2] Prompt Negativo Global:")
        print(f"    {self.config_activa['prompt_negativo_global']}")

        print("\nOpciones:")
        print("1. Modificar Estilo Global (Positivo)")
        print("2. Modificar Prompt Negativo Global")
        print("3. Volver")

        op = input("Seleccione una opción: ").strip()
        if op == "1":
            nuevo_estilo = input("\nIngrese el nuevo Estilo Global: ").strip()
            if nuevo_estilo:
                self.config_activa["estilo_global"] = nuevo_estilo
                self.storage.guardar_config(self.proyecto_activo, self.config_activa)
                print("[OK] Estilo Global actualizado correctamente.")
        elif op == "2":
            nuevo_neg = input("\nIngrese el nuevo Prompt Negativo Global: ").strip()
            if nuevo_neg:
                self.config_activa["prompt_negativo_global"] = nuevo_neg
                self.storage.guardar_config(self.proyecto_activo, self.config_activa)
                print("[OK] Prompt Negativo Global actualizado correctamente.")

    def menu_gestion_personajes(self):
        while True:
            print("\n--- GESTIÓN DE PERSONAJES ---")
            print("1. Añadir nuevo personaje")
            print("2. Listar personajes registrados")
            print("3. Volver")

            op = input("Seleccione una opción: ").strip()
            if op == "1":
                char_id = input("ID del personaje (ej: 01_narrador): ").strip()
                nombre = input("Nombre legible (ej: Narrador / Protagonista): ").strip()
                actor_voz = input("ID Actor Voz TTS (ej: es-MX-JorgeNeural): ").strip()

                print("\nPrompts base del personaje:")
                prompt_pos = input("Prompt Positivo Base (atributos físicos, ropa): ").strip()
                prompt_neg = input("Prompt Negativo Base (filtros específicos adicionales, opcional): ").strip()

                self.storage.crear_carpeta_personaje(self.proyecto_activo, char_id)

                self.config_activa["personajes"][char_id] = {
                    "id": char_id,
                    "nombre": nombre,
                    "actor_voz": actor_voz,
                    "prompt_positivo_base": prompt_pos,
                    "prompt_negativo_base": prompt_neg,
                }

                self.storage.guardar_config(self.proyecto_activo, self.config_activa)
                print(f"[OK] Personaje '{char_id}' registrado.")
            elif op == "2":
                personajes = self.config_activa["personajes"]
                if not personajes:
                    print("[INFO] No hay personajes registrados.")
                else:
                    for cid, pdata in personajes.items():
                        imgs = self.storage.obtener_imagenes_referencia(self.proyecto_activo, cid)
                        print(f"\nID: {cid} | Nombre: {pdata['nombre']}")
                        print(f"Voz: {pdata['actor_voz']}")
                        print(f"Imágenes de referencia listas: {len(imgs)}")
            elif op == "3":
                break

    def menu_gestion_escenas(self):
        while True:
            print("\n--- GESTIÓN DE ESCENAS ---")
            print("1. Registrar nueva escena")
            print("2. Listar escenas")
            print("3. Volver")

            op = input("Seleccione una opción: ").strip()
            if op == "1":
                personajes = self.config_activa["personajes"]
                if not personajes:
                    print("[ERROR] Registre al menos un personaje antes de crear escenas.")
                    return

                print("\nSeleccione el personaje principal de la escena:")
                keys = list(personajes.keys())
                for idx, k in enumerate(keys, 1):
                    print(f"{idx}. {k} ({personajes[k]['nombre']})")
                sel = input("Número: ").strip()
                if not (sel.isdigit() and 1 <= int(sel) <= len(keys)):
                    print("[ERROR] Selección inválida.")
                    continue
                char_id = keys[int(sel) - 1]

                escena_id = f"escena_{len(self.config_activa['escenas']) + 1:02d}"
                dialogo = input("Texto del guión para esta toma (narración de voz): ").strip()
                accion = input("Acción visual/entorno (Prompt de la escena en inglés): ").strip()

                nueva_escena = {
                    "id": escena_id,
                    "personaje_id": char_id,
                    "dialogo": dialogo,
                    "accion_prompt": accion,
                    "estado": "pendiente",
                }

                self.config_activa["escenas"].append(nueva_escena)
                self.storage.guardar_config(self.proyecto_activo, self.config_activa)
                print(f"[OK] Escena '{escena_id}' registrada.")
            elif op == "2":
                escenas = self.config_activa["escenas"]
                if not escenas:
                    print("[INFO] No hay escenas creadas.")
                else:
                    for e in escenas:
                        print(f"\nID: {e['id']} | Personaje: {e['personaje_id']} | Estado: {e['estado']}")
                        print(f"Guión: {e['dialogo']}")
                        print(f"Acción (Prompt): {e['accion_prompt']}")
            elif op == "3":
                break

    def menu_ejecutar_workflow_a(self):
        personajes = self.config_activa["personajes"]
        if not personajes:
            print("[ERROR] Registre al menos un personaje.")
            return

        print("\nSeleccione el personaje para GENERAR imágenes estáticas de referencia:")
        keys = list(personajes.keys())
        for idx, k in enumerate(keys, 1):
            print(f"{idx}. {k} ({personajes[k]['nombre']})")

        sel = input("Número: ").strip()
        if not (sel.isdigit() and 1 <= int(sel) <= len(keys)):
            print("[ERROR] Selección inválida.")
            return

        char_id = keys[int(sel) - 1]
        pdata = personajes[char_id]

        prompt_pos = PromptBuilder.construir_prompt_positivo(
            self.config_activa["estilo_global"], pdata["prompt_positivo_base"]
        )
        prompt_neg = PromptBuilder.construir_prompt_negativo(
            self.config_activa["prompt_negativo_global"], pdata["prompt_negativo_base"]
        )
        target_prefix = f"projects/{self.proyecto_activo}/01_assets/personajes/{char_id}/ref_images/ref"

        try:
            wf_json = self.orchestrator.construir_workflow_a(self.proyecto_activo, prompt_pos, prompt_neg, target_prefix)
        except Exception as e:
            print(f"[ERROR] No se pudo cargar la plantilla del proyecto: {e}")
            return

        print("\nEnviando Workflow A a ComfyUI (127.0.0.1:8188)...")
        exito, prompt_id = self.api_client.enviar_prompt(wf_json)

        if exito:
            print(f"[ÉXITO] Tarea enviada. Prompt ID: {prompt_id}")
            print(f"Imágenes generándose en: {self.storage.comfy_dir / 'output' / target_prefix}_XXXX_.png")
        else:
            print(f"[ERROR] Fallo al conectar con ComfyUI: {prompt_id}")

    def menu_ejecutar_workflow_b(self):
        escenas = self.config_activa["escenas"]
        if not escenas:
            print("[ERROR] Registre al menos una escena.")
            return

        print("\nSeleccione la escena a renderizar en VIDEO:")
        for idx, e in enumerate(escenas, 1):
            print(f"{idx}. {e['id']} | Personaje: {e['personaje_id']} | Guión: {e['dialogo'][:40]}...")

        sel = input("Número: ").strip()
        if not (sel.isdigit() and 1 <= int(sel) <= len(escenas)):
            print("[ERROR] Selección inválida.")
            return

        escena = escenas[int(sel) - 1]
        char_id = escena["personaje_id"]
        pdata = self.config_activa["personajes"][char_id]

        rutas_input = self.storage.preparar_todas_referencias_para_input(self.proyecto_activo, char_id)
        if not rutas_input:
            print(f"[ERROR] El personaje '{char_id}' no tiene imágenes en 'ref_images'. Genere primero el Workflow A.")
            return

        print(f"\n[INFO] Se utilizará la imagen base: {rutas_input[0]} (LTX-Video toma 1 frame inicial).")

        prompt_pos = PromptBuilder.construir_prompt_positivo(
            self.config_activa["estilo_global"],
            pdata["prompt_positivo_base"],
            escena["accion_prompt"],
        )
        prompt_neg = PromptBuilder.construir_prompt_negativo(
            self.config_activa["prompt_negativo_global"],
            pdata["prompt_negativo_base"]
        )
        target_prefix = f"projects/{self.proyecto_activo}/03_renders/{escena['id']}"

        try:
            wf_json = self.orchestrator.construir_workflow_b(self.proyecto_activo, prompt_pos, prompt_neg, rutas_input, target_prefix)
        except Exception as e:
            print(f"[ERROR] No se pudo cargar la plantilla del proyecto: {e}")
            return

        print(f"\nEnviando render de video LTX I2V de '{escena['id']}' a ComfyUI...")
        exito, prompt_id = self.api_client.enviar_prompt(wf_json)

        if exito:
            escena["estado"] = "renderizando"
            self.storage.guardar_config(self.proyecto_activo, self.config_activa)
            print(f"[ÉXITO] Render enviado a ComfyUI. Prompt ID: {prompt_id}")
            print(f"El video se guardará en: {self.storage.comfy_dir / 'output' / target_prefix}_00001_.mp4")
        else:
            print(f"[ERROR] Fallo al conectar con ComfyUI: {prompt_id}")

    def menu_diagnostico(self):
        print(f"\n--- DIAGNÓSTICO: {self.proyecto_activo} ---")
        print(f"Directorio ComfyUI: {self.storage.comfy_dir}")
        print(f"Preset Usado: {self.config_activa.get('preset_usado', 'personalizado')}")
        print(f"Estilo Global (Positivo): {self.config_activa['estilo_global']}")
        print(f"Prompt Negativo Global: {self.config_activa['prompt_negativo_global']}")
        personajes = self.config_activa["personajes"]
        escenas = self.config_activa["escenas"]
        print(f"Total Personajes: {len(personajes)}")
        print(f"Total Escenas: {len(escenas)}")

        print("\nEstado de Personajes:")
        for cid in personajes:
            imgs = self.storage.obtener_imagenes_referencia(self.proyecto_activo, cid)
            estado = f"LISTO ({len(imgs)} refs)" if len(imgs) >= 1 else "PENDIENTE (Sin referencias)"
            print(f" - {cid}: [{estado}]")

        print("\nEstado de Escenas:")
        for e in escenas:
            print(f" - {e['id']} ({e['personaje_id']}): {e['estado']}")


if __name__ == "__main__":
    app = CLIInterface()
    app.iniciar()