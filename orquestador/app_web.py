import os
import sys
import threading
from pathlib import Path

# Agregar directorio del orquestador al sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import gradio as gr
from config import INPUT_DIR, OUTPUT_DIR
from core.storage_engine import StorageEngine
from core.comfy_client import ComfyAPIClient
from modules.guion_manager import GuionManager
from modules.tts_engine import TTSEngine
from modules.image_engine import ImageEngine
from modules.video_engine import VideoEngine
from modules.broll_engine import BRollAnimationEngine
from modules.sadtalker_engine import SadTalkerEngine
from modules.subtitle_engine import SubtitleEngine
from modules.assembly_engine import AssemblyEngine

storage = StorageEngine()
api_client = ComfyAPIClient()

# Generar lista de opciones de voz para el selector
tts_dummy = TTSEngine(storage, "temp")
VOCES_CHOICES = ["(Usar del guion)"]
for idioma, v_dict in tts_dummy.VOCES_DISPONIBLES.items():
    for v_id, v_desc in v_dict.items():
        VOCES_CHOICES.append(f"{v_id} - {v_desc}")


def obtener_proyectos():
    projs = storage.listar_proyectos()
    return projs if projs else ["(Sin proyectos)"]


def obtener_estado_proyecto(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto válido para ver el estado.", "", None, None

    try:
        config = storage.cargar_config(proyecto_id)
    except Exception as e:
        return f"Error leyendo configuración: {e}", "", None, None

    input_dir = INPUT_DIR / proyecto_id
    output_dir = OUTPUT_DIR / proyecto_id

    escenas = config.get("escenas", [])
    personajes = config.get("personajes", {})
    escenas_p = [e for e in escenas if e.get("tipo") == "personaje"]
    escenas_b = [e for e in escenas if e.get("tipo") == "b_roll"]

    audios_dir = input_dir / "audios"
    audios_listos = sum(1 for e in escenas if (audios_dir / f"{e['id']}.wav").exists())

    ref_in = input_dir / "ref_images"
    ref_out = output_dir / "ref_images"
    masters_listos = sum(
        1 for p_id in personajes
        if (ref_in / f"master_{p_id}.png").exists() or (ref_out / f"master_{p_id}.png").exists()
    )
    imgs_p = sum(
        1 for e in escenas_p
        if list(ref_in.glob(f"{e['id']}_personaje*.png")) or list(ref_out.glob(f"{e['id']}_personaje*.png"))
    )
    imgs_b = sum(
        1 for e in escenas_b
        if list(ref_in.glob(f"{e['id']}_b_roll*.png")) or list(ref_out.glob(f"{e['id']}_b_roll*.png"))
    )

    sadtalker_dir = output_dir / "sadtalker_temp"
    driving_listos = sum(1 for e in escenas_p if (sadtalker_dir / f"{e['id']}_driving.mp4").exists())

    renders_dir = output_dir / "renders"
    broll_listos = sum(1 for e in escenas_b if (renders_dir / f"{e['id']}_final.mp4").exists())
    lp_listos = sum(
        1 for e in escenas_p
        if (renders_dir / f"{e['id']}_enhanced.mp4").exists() or (renders_dir / f"{e['id']}_final.mp4").exists()
    )

    sub_dir = output_dir / "subtitles"
    sub_ok = (sub_dir / f"{proyecto_id}_normal.srt").exists()

    final_dir = output_dir / "final"
    video_pelicula = None
    if final_dir.exists():
        candidatos = list(final_dir.glob("*.mp4"))
        if candidatos:
            video_pelicula = str(candidatos[0])

    resumen = f"""### 📊 Dashboard: `{proyecto_id}`
- **Preset de Estilo:** {config.get('preset_usado', 'N/A')}
- **Escenas Totales:** {len(escenas)} ({len(escenas_p)} personajes, {len(escenas_b)} B-Roll)
- **Personajes:** {len(personajes)} ({masters_listos} Maestras listas)
- **Audios TTS:** {audios_listos}/{len(escenas)}
- **Imágenes HD:** {imgs_p + imgs_b}/{len(escenas)}
- **Driving SadTalker:** {driving_listos}/{len(escenas_p)}
- **B-Roll Animado:** {broll_listos}/{len(escenas_b)}
- **LivePortrait HD:** {lp_listos}/{len(escenas_p)}
- **Subtítulos SRT:** {'✓ Exportados' if sub_ok else 'Pendiente'}
- **Película Final:** {'✓ Generada' if video_pelicula else 'Pendiente'}
"""
    guion_preview = f"Guion cargado con {len(escenas)} escenas y {len(personajes)} personajes."
    return resumen, guion_preview, video_pelicula, gr.update(choices=obtener_escenas_choices(proyecto_id))


def obtener_escenas_choices(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return []
    try:
        config = storage.cargar_config(proyecto_id)
        escenas = config.get("escenas", [])
        return [f"{e['id']} ({e.get('tipo', 'escena')}): {e.get('dialogo', '')[:35]}..." for e in escenas]
    except Exception:
        return []


def resolver_voz_seleccionada(voz_str: str, voz_manual: str) -> str:
    if voz_manual and voz_manual.strip():
        return voz_manual.strip()
    if not voz_str or voz_str == "(Usar del guion)":
        return None
    return voz_str.split(" - ")[0].strip()


# ========================================================
# ACCIONES DEL PIPELINE
# ========================================================

def run_fase_guion(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        gm = GuionManager(storage, proyecto_id)
        gm.cargar_guion_desde_json()
        return f"[ÉXITO] Guion de '{proyecto_id}' cargado y sincronizado."
    except Exception as e:
        return f"[ERROR] Guion: {e}"


def run_fase_tts(proyecto_id: str, voz_sel: str, voz_manual: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        voz = resolver_voz_seleccionada(voz_sel, voz_manual)
        tts = TTSEngine(storage, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        escenas = config.get("escenas", [])
        logs = []
        for esc in escenas:
            arch, dur = tts.procesar_escena(esc["id"], voz_override=voz)
            if arch:
                logs.append(f"✓ {esc['id']}: {arch} ({dur:.2f}s)")
        return f"[ÉXITO TTS]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR TTS] {e}"


def run_fase_imagenes(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        img_engine = ImageEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        # Masters
        for p_id, p_data in config.get("personajes", {}).items():
            img_engine.asegurar_imagen_maestra_personaje(p_id, p_data)
            logs.append(f"✓ Master {p_id} OK")
        # Escenas
        for esc in config.get("escenas", []):
            e_id = esc["id"]
            if esc.get("tipo") == "personaje":
                img_engine.renderizar_escena_personaje(e_id)
                logs.append(f"✓ Escena personaje {e_id} renderizada")
            elif esc.get("tipo") == "b_roll":
                img_engine.renderizar_escena_broll(e_id)
                logs.append(f"✓ Escena B-Roll {e_id} renderizada")
        return f"[ÉXITO IMÁGENES]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR IMÁGENES] {e}"


def run_fase_sadtalker(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        api_client.liberar_memoria()
        sadtalker = SadTalkerEngine(proyecto_id)
        config = storage.cargar_config(proyecto_id)
        personajes = config.get("personajes", {})
        logs = []
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                p_id = esc.get("personaje_id")
                avatar = personajes.get(p_id, {}).get("avatar") or "man.png"
                out = sadtalker.generar_video_borrador(e_id, avatar, f"{e_id}.wav")
                logs.append(f"✓ Driving SadTalker listo: {out.name}")
        return f"[ÉXITO SADTALKER]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR SADTALKER] {e}"


def run_fase_broll(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        broll = BRollAnimationEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "b_roll":
                out = broll.animar_escena_broll(esc["id"])
                logs.append(f"✓ B-Roll animado: {out.name}")
        return f"[ÉXITO B-ROLL]\n" + ("\n".join(logs) if logs else "Sin escenas B-Roll.")
    except Exception as e:
        return f"[ERROR B-ROLL] {e}"


def run_fase_liveportrait(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        vid_engine = VideoEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                exito, p_id = vid_engine.renderizar_lipsync(e_id, f"{e_id}_personaje_00001_.png", f"{e_id}_driving.mp4")
                logs.append(f"✓ LivePortrait {e_id} completado")
        return f"[ÉXITO LIVEPORTRAIT]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR LIVEPORTRAIT] {e}"


def run_fase_subtitulos(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero."
    try:
        sub_engine = SubtitleEngine(storage, proyecto_id)
        res = sub_engine.generar_subtitulos_timeline_completo()
        return f"[ÉXITO SUBTÍTULOS]\nArchivos generados:\n- {res['normal'].name}\n- {res['highlights'].name}\n- {res['en'].name}"
    except Exception as e:
        return f"[ERROR SUBTÍTULOS] {e}"


def run_fase_assembly(proyecto_id: str, nombre_out: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero.", None
    try:
        nombre = nombre_out.strip() if nombre_out else "pelicula_completa.mp4"
        if not nombre.endswith(".mp4"):
            nombre += ".mp4"
        assembly = AssemblyEngine(proyecto_id, storage)
        out = assembly.ensamblar_pelicula(nombre_salida=nombre)
        return f"[ÉXITO ENSAMBLAJE] Película exportada: {out.name}", str(out)
    except Exception as e:
        return f"[ERROR ENSAMBLAJE] {e}", None


def run_pipeline_completo(proyecto_id: str, voz_sel: str, voz_manual: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "Seleccione un proyecto primero.", None
    logs = ["=== INICIANDO PIPELINE AUTOMATIZADO COMPLETO ==="]
    try:
        voz = resolver_voz_seleccionada(voz_sel, voz_manual)
        # 1. Guion
        logs.append("\n[1/7] Cargando Guion...")
        gm = GuionManager(storage, proyecto_id)
        gm.cargar_guion_desde_json()
        config = storage.cargar_config(proyecto_id)
        logs.append(f"✓ Guion cargado: {len(config.get('escenas', []))} escenas.")

        # 2. TTS
        logs.append(f"\n[2/7] Generando TTS (Voz: {voz or 'Guion'})...")
        tts = TTSEngine(storage, proyecto_id)
        for esc in config.get("escenas", []):
            tts.procesar_escena(esc["id"], voz_override=voz)
        logs.append("✓ Pistas de audio completadas.")

        # 3. Imágenes
        logs.append("\n[3/7] Renderizando Imágenes HD (SDXL)...")
        img_engine = ImageEngine(storage, api_client, proyecto_id)
        for p_id, p_data in config.get("personajes", {}).items():
            img_engine.asegurar_imagen_maestra_personaje(p_id, p_data)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                img_engine.renderizar_escena_personaje(esc["id"])
            elif esc.get("tipo") == "b_roll":
                img_engine.renderizar_escena_broll(esc["id"])
        logs.append("✓ Imágenes generadas.")

        # 4. SadTalker
        logs.append("\n[4/7] Generando Driving Videos (SadTalker)...")
        api_client.liberar_memoria()
        sadtalker = SadTalkerEngine(proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                p_id = esc.get("personaje_id")
                avatar = config.get("personajes", {}).get(p_id, {}).get("avatar") or "man.png"
                sadtalker.generar_video_borrador(e_id, avatar, f"{e_id}.wav")
        logs.append("✓ Driving videos listos.")

        # 4b. B-Roll
        logs.append("\n[5/7] Animando escenas B-Roll (SVD + RIFE)...")
        broll = BRollAnimationEngine(storage, api_client, proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "b_roll":
                broll.animar_escena_broll(esc["id"])
        logs.append("✓ B-Roll animado.")

        # 5. LivePortrait
        logs.append("\n[6/7] Procesando LivePortrait HD y Masterizado...")
        vid_engine = VideoEngine(storage, api_client, proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                vid_engine.renderizar_lipsync(e_id, f"{e_id}_personaje_00001_.png", f"{e_id}_driving.mp4")
        logs.append("✓ LivePortrait masterizado.")

        # 6. Subtítulos
        logs.append("\n[7/7] Generando Pistas SRT Maestras...")
        sub_engine = SubtitleEngine(storage, proyecto_id)
        sub_engine.generar_subtitulos_timeline_completo()
        logs.append("✓ Subtítulos generados.")

        # 7. Ensamblaje
        logs.append("\n[FINAL] Ensamblando Película Completa...")
        assembly = AssemblyEngine(proyecto_id, storage)
        out = assembly.ensamblar_pelicula(nombre_salida="pelicula_completa.mp4")
        logs.append(f"\n🎉 ¡PIPELINE FINALIZADO CON ÉXITO! Película: {out.name}")
        return "\n".join(logs), str(out)
    except Exception as e:
        logs.append(f"\n❌ ERROR EN PIPELINE: {e}")
        return "\n".join(logs), None


# ========================================================
# CONSTRUCCIÓN DE INTERFAZ GRADIO
# ========================================================

tema = gr.themes.Soft(
    primary_hue="cyan",
    secondary_hue="slate",
    neutral_hue="neutral"
)

with gr.Blocks(title="Orquestador de Video IA - Studio Web") as demo:
    gr.Markdown("""
    # 🎬 Orquestador de Video IA — Studio Web
    ### Pipeline Automatizado HD: ComfyUI + Kokoro TTS + SadTalker + LivePortrait + DaVinci SRT
    """)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### 📁 Selección de Proyecto")
                dropdown_proyectos = gr.Dropdown(
                    label="Proyecto Activo",
                    choices=obtener_proyectos(),
                    value=obtener_proyectos()[0] if obtener_proyectos() else "(Sin proyectos)"
                )
                btn_recargar_proyectos = gr.Button("🔄 Refrescar Lista", size="sm")

            with gr.Group():
                gr.Markdown("### 🎙️ Configuración de Voz (Kokoro-82M)")
                dropdown_voz = gr.Dropdown(
                    label="Voz para el Pipeline",
                    choices=VOCES_CHOICES,
                    value="(Usar del guion)",
                    info="Seleccione una voz para sobreescribir el guion o déjelo en predeterminado."
                )
                input_voz_manual = gr.Textbox(
                    label="Fórmula Voice Blending (Opcional)",
                    placeholder="ej: em_alex:0.7+am_fenrir:0.3",
                    info="Si se llena, tiene prioridad absoluta sobre la lista."
                )

        with gr.Column(scale=2):
            dashboard_md = gr.Markdown("Cargando estado del proyecto...")
            video_preview = gr.Video(label="Película Ensamblada (Vista Previa)", interactive=False)

    with gr.Tabs():
        with gr.TabItem("⚡ Pipeline Automatizado Completo"):
            gr.Markdown("Ejecuta de manera secuencial y sincronizada todas las fases (1 a 8).")
            btn_run_all = gr.Button("🚀 EJECUTAR PIPELINE COMPLETO AUTOMATIZADO", variant="primary", size="lg")
            log_all = gr.Textbox(label="Consola de Ejecución en Vivo", lines=12, max_lines=25)

        with gr.TabItem("🎛️ Control Manual por Fases"):
            gr.Markdown("Ejecuta fases individuales de manera independiente para iterar o revisar.")
            with gr.Row():
                btn_fase1 = gr.Button("1. Cargar Guion", size="sm")
                btn_fase2 = gr.Button("2. Generar Audios TTS", size="sm")
                btn_fase3 = gr.Button("3. Renderizar Imágenes", size="sm")
            with gr.Row():
                btn_fase4 = gr.Button("4. Driving SadTalker", size="sm")
                btn_fase4b = gr.Button("5. Animación B-Roll", size="sm")
                btn_fase5 = gr.Button("6. LivePortrait HD", size="sm")
            with gr.Row():
                btn_fase6 = gr.Button("7. Subtítulos SRT", size="sm")
                btn_fase7 = gr.Button("8. Ensamblar Película", size="sm")

            input_nombre_ensamble = gr.Textbox(label="Nombre salida video ensamblado", value="pelicula_completa.mp4")
            log_fases = gr.Textbox(label="Registro de la Fase", lines=8)

    # ========================================================
    # EVENTOS Y ENLACES
    # ========================================================

    def refrescar_todo(p_id):
        res, guion, vid, escenas_up = obtener_estado_proyecto(p_id)
        return res, vid

    dropdown_proyectos.change(
        refrescar_todo,
        inputs=[dropdown_proyectos],
        outputs=[dashboard_md, video_preview]
    )

    btn_recargar_proyectos.click(
        lambda: gr.update(choices=obtener_proyectos()),
        outputs=[dropdown_proyectos]
    )

    # Ejecución completa
    btn_run_all.click(
        run_pipeline_completo,
        inputs=[dropdown_proyectos, dropdown_voz, input_voz_manual],
        outputs=[log_all, video_preview]
    ).then(
        refrescar_todo,
        inputs=[dropdown_proyectos],
        outputs=[dashboard_md, video_preview]
    )

    # Fases individuales
    btn_fase1.click(run_fase_guion, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase2.click(run_fase_tts, inputs=[dropdown_proyectos, dropdown_voz, input_voz_manual], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase3.click(run_fase_imagenes, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase4.click(run_fase_sadtalker, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase4b.click(run_fase_broll, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase5.click(run_fase_liveportrait, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase6.click(run_fase_subtitulos, inputs=[dropdown_proyectos], outputs=[log_fases]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )
    btn_fase7.click(run_fase_assembly, inputs=[dropdown_proyectos, input_nombre_ensamble], outputs=[log_fases, video_preview]).then(
        refrescar_todo, inputs=[dropdown_proyectos], outputs=[dashboard_md, video_preview]
    )

    # Carga inicial al abrir
    demo.load(
        refrescar_todo,
        inputs=[dropdown_proyectos],
        outputs=[dashboard_md, video_preview]
    )

if __name__ == "__main__":
    puerto = 7860
    print(f"\n[INFO] Iniciando Interfaz Web en http://127.0.0.1:{puerto} ...")
    demo.launch(server_name="127.0.0.1", server_port=puerto, inbrowser=True, theme=tema)
