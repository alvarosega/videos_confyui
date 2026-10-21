import json
import urllib.request
import urllib.parse
import time
import os

SERVER_ADDRESS = "127.0.0.1:8188"
RUTA_WORKFLOW_JSON = r"C:\ia-video\orquestador\workflow_api.json"
CARPETA_RENDERS = r"C:\ia-video\ComfyUI\output"

DEFAULT_STYLE_POSITIVE = "cinematic 3d render, octane render, unreal engine 5, photorealistic CGI, 8k resolution, highly detailed, magical lighting, depth of field, sharp focus, masterpiece"
DEFAULT_STYLE_NEGATIVE = "real photo, live action, worst quality, low quality, 2d, anime, cartoon, sketch, blurry, bad anatomy, extra limbs, static image, text, watermark"

def cargar_workflow_base():
    if not os.path.exists(RUTA_WORKFLOW_JSON):
        raise FileNotFoundError(f"[ERROR] No existe el archivo del workflow: {RUTA_WORKFLOW_JSON}")
    with open(RUTA_WORKFLOW_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def buscar_nodo(workflow, class_type=None, title=None):
    for node_id, node_data in workflow.items():
        meta_title = node_data.get("_meta", {}).get("title", "")
        node_class = node_data.get("class_type", "")
        if title and title == meta_title:
            return node_id, node_data
        if class_type and node_class == class_type and not title:
            return node_id, node_data
    raise KeyError(f"[ERROR_DIAGNOSTICO] Nodo no hallado: class_type='{class_type}', title='{title}'")

def limpiar_renders_previos(prefix_escena):
    if os.path.exists(CARPETA_RENDERS):
        for f in os.listdir(CARPETA_RENDERS):
            if f.startswith(prefix_escena) and f.endswith(".mp4"):
                try:
                    os.remove(os.path.join(CARPETA_RENDERS, f))
                except OSError:
                    pass

def preparar_prompt_json(prompt_texto, frames, id_escena, semilla, width=512, height=512, style_pos=None, style_neg=None):
    workflow = cargar_workflow_base()
    
    pos_style = style_pos if style_pos is not None else DEFAULT_STYLE_POSITIVE
    neg_style = style_neg if style_neg is not None else DEFAULT_STYLE_NEGATIVE
    prompt_final = f"{prompt_texto}, {pos_style}".strip(", ")

    _, nodo_pos = buscar_nodo(workflow, title="Codificar Texto CLIP (Prompt)")
    _, nodo_neg = buscar_nodo(workflow, title="Codificar Texto CLIP (Negative)")
    _, nodo_latent = buscar_nodo(workflow, class_type="EmptyLatentImage")
    _, nodo_sampler = buscar_nodo(workflow, class_type="KSampler")
    _, nodo_video = buscar_nodo(workflow, class_type="VHS_VideoCombine")
    
    try:
        _, nodo_anim = buscar_nodo(workflow, class_type="ADE_UseEvolvedSampling")
        nodo_anim["inputs"]["beta_schedule"] = "sqrt_linear (AnimateDiff)"
    except KeyError:
        pass

    nodo_pos["inputs"]["text"] = prompt_final
    nodo_neg["inputs"]["text"] = neg_style

    nodo_latent["inputs"]["batch_size"] = frames
    nodo_latent["inputs"]["width"] = width
    nodo_latent["inputs"]["height"] = height

    # Muestreador determinista DDIM para evitar inyección estocástica de ruido
    nodo_sampler["inputs"]["seed"] = semilla
    nodo_sampler["inputs"]["cfg"] = 6.0
    nodo_sampler["inputs"]["sampler_name"] = "ddim"
    nodo_sampler["inputs"]["scheduler"] = "normal"

    # ⚠️ Corrección de seguridad para AnimateDiff
    try:
        _, nodo_context = buscar_nodo(workflow, class_type="ADE_StandardStaticContextOptions")
        # Obligamos a que el modelo de movimiento se aplique incluso cuando frames == context_length
        nodo_context["inputs"]["use_on_equal_length"] = True
        # Si context_length es mayor que los frames, lo ajustamos automáticamente
        if nodo_context["inputs"]["context_length"] > frames:
            nodo_context["inputs"]["context_length"] = frames
            nodo_context["inputs"]["context_overlap"] = max(2, frames // 4)
            print(f"[AVISO] context_length ajustado a {frames} (context_overlap={nodo_context['inputs']['context_overlap']})")
    except KeyError:
        pass

    nodo_video["inputs"]["filename_prefix"] = f"escena_{id_escena:03d}"

    print(f"\n--- TELEMETRÍA DEL PAYLOAD (ESCENA {id_escena:02d}) ---")
    print(f"Prompt Positivo : {prompt_final}")
    print(f"Prompt Negativo : {neg_style}")
    print(f"Dimensiones Latentes: {width}x{height} | Batch size (Frames): {frames}")
    print(f"Config Sampler  : ddim | Scheduler: normal | CFG: 6.0 | Seed: {semilla}")
    print(f"Beta Schedule   : sqrt_linear (AnimateDiff)")
    print(f"---------------------------------------------------\n")

    return workflow

def enviar_prompt_comfyui(prompt_config):
    p = {"prompt": prompt_config}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"\n[ERROR HTTP {e.code} API COMFYUI]")
        print(f"Detalle de validación devuelto por ComfyUI:\n{error_body}")
        raise RuntimeError(f"Rechazo de payload por ComfyUI: {error_body}")

def obtener_historial(prompt_id):
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/history/{prompt_id}")
    response = urllib.request.urlopen(req)
    return json.loads(response.read())

def esperar_render(prompt_id, timeout_segundos=1800):
    inicio = time.time()
    
    while time.time() - inicio < timeout_segundos:
        historial = obtener_historial(prompt_id)
        
        if prompt_id in historial:
            data = historial[prompt_id]
            status_info = data.get("status", {})
            completed = status_info.get("completed", False)
            messages = status_info.get("messages", [])
            
            if not completed or status_info.get("status_str") == "error":
                print(f"\n[ERROR EN MOTOR COMFYUI] Prompt ID: {prompt_id}")
                print(f"Registro de errores del ejecutor: {messages}")
                raise RuntimeError(f"Falla de ejecución interna en ComfyUI: {messages}")
            
            print(f"[EXITO] Renderizado completado correctamente en {int(time.time() - inicio)}s.")
            return data

        time.sleep(2)
        
    raise TimeoutError("[ERROR_TIMEOUT] El tiempo de renderizado superó el límite establecido.")

def procesar_escena_comfyui(id_escena, prompt_texto, frames, semilla, width=512, height=512, style_pos=None, style_neg=None):
    prefix = f"escena_{id_escena:03d}"
    limpiar_renders_previos(prefix)
    
    config = preparar_prompt_json(prompt_texto, frames, id_escena, semilla, width, height, style_pos, style_neg)
    respuesta = enviar_prompt_comfyui(config)
    prompt_id = respuesta.get("prompt_id")
    
    if not prompt_id:
        raise ValueError("[ERROR] ComfyUI no generó un prompt_id válido.")
        
    print(f"[ENVIADO] Petición aceptada por el servidor. Prompt ID: {prompt_id}")
    resultado = esperar_render(prompt_id)
    return resultado

if __name__ == "__main__":
    print("Módulo Conector ComfyUI cargado.")