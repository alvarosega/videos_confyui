import os
import sys
from pathlib import Path

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
        return "Seleccione un proyecto para visualizar metricas.", "", None

    try:
        config = storage.cargar_config(proyecto_id)
    except Exception as e:
        return f"Error leyendo configuracion: {e}", "", None

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

    resumen = f"""| Modulo Operativo | Progreso | Estado |
| :--- | :---: | :--- |
| **Guion y Escenas** | {len(escenas)} | {'Completado' if escenas else 'Pendiente'} |
| **Personajes Registrados** | {len(personajes)} | {masters_listos}/{len(personajes)} Retratos Maestros |
| **Audios TTS (Kokoro)** | {audios_listos}/{len(escenas)} | {'Completado' if audios_listos == len(escenas) and len(escenas) > 0 else 'Parcial'} |
| **Imagenes HD (SDXL)** | {imgs_p + imgs_b}/{len(escenas)} | {'Completado' if (imgs_p + imgs_b) == len(escenas) and len(escenas) > 0 else 'Parcial'} |
| **Driving SadTalker** | {driving_listos}/{len(escenas_p)} | {'Completado' if driving_listos == len(escenas_p) and len(escenas_p) > 0 else 'Parcial'} |
| **Animacion B-Roll (SVD)** | {broll_listos}/{len(escenas_b)} | {'Completado' if broll_listos == len(escenas_b) and len(escenas_b) > 0 else 'Sin B-Roll'} |
| **LivePortrait HD (Lipsync)** | {lp_listos}/{len(escenas_p)} | {'Completado' if lp_listos == len(escenas_p) and len(escenas_p) > 0 else 'Parcial'} |
| **Subtitulos SRT** | {'3 Pistas' if sub_ok else '0'} | {'Generados (DaVinci)' if sub_ok else 'Pendiente'} |
| **Master de Pelicula** | {'1 Archivo' if video_pelicula else '0'} | {'Exportado' if video_pelicula else 'Pendiente'} |

**Preset:** `{config.get('preset_usado', 'N/A')}` | **Resolucion:** `{config.get('resolucion', '512x768')}`
"""
    guion_preview = f"Proyecto: {proyecto_id} | Escenas: {len(escenas)} | Entidades: {len(personajes)}"
    return resumen, guion_preview, video_pelicula


def resolver_voz_seleccionada(voz_str: str, voz_manual: str) -> str:
    if voz_manual and voz_manual.strip():
        return voz_manual.strip()
    if not voz_str or voz_str == "(Usar del guion)":
        return None
    return voz_str.split(" - ")[0].strip()


def run_fase_guion(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        gm = GuionManager(storage, proyecto_id)
        gm.cargar_guion_desde_json()
        return f"[EXITO] Guion de '{proyecto_id}' cargado y sincronizado."
    except Exception as e:
        return f"[ERROR] Guion: {e}"


def run_fase_tts(proyecto_id: str, voz_sel: str, voz_manual: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        voz = resolver_voz_seleccionada(voz_sel, voz_manual)
        tts = TTSEngine(storage, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        escenas = config.get("escenas", [])
        logs = []
        for esc in escenas:
            arch, dur = tts.procesar_escena(esc["id"], voz_override=voz)
            if arch:
                logs.append(f"[OK] {esc['id']}: {arch} ({dur:.2f}s)")
        return "[EXITO TTS]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR TTS] {e}"


def run_fase_imagenes(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        img_engine = ImageEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        for p_id, p_data in config.get("personajes", {}).items():
            img_engine.asegurar_imagen_maestra_personaje(p_id, p_data)
            logs.append(f"[OK] Retrato Maestro: {p_id}")
        for esc in config.get("escenas", []):
            e_id = esc["id"]
            if esc.get("tipo") == "personaje":
                img_engine.renderizar_escena_personaje(e_id)
                logs.append(f"[OK] Escena personaje: {e_id}")
            elif esc.get("tipo") == "b_roll":
                img_engine.renderizar_escena_broll(e_id)
                logs.append(f"[OK] Escena B-Roll: {e_id}")
        return "[EXITO IMAGENES]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR IMAGENES] {e}"


def run_fase_sadtalker(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
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
                logs.append(f"[OK] Driving video: {out.name}")
        return "[EXITO SADTALKER]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR SADTALKER] {e}"


def run_fase_broll(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        broll = BRollAnimationEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "b_roll":
                out = broll.animar_escena_broll(esc["id"])
                logs.append(f"[OK] B-Roll animado: {out.name}")
        return "[EXITO B-ROLL]\n" + ("\n".join(logs) if logs else "Sin escenas B-Roll.")
    except Exception as e:
        return f"[ERROR B-ROLL] {e}"


def run_fase_liveportrait(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        vid_engine = VideoEngine(storage, api_client, proyecto_id)
        config = storage.cargar_config(proyecto_id)
        logs = []
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                exito, p_id = vid_engine.renderizar_lipsync(e_id, f"{e_id}_personaje_00001_.png", f"{e_id}_driving.mp4")
                logs.append(f"[OK] LivePortrait HD masterizado: {e_id}")
        return "[EXITO LIVEPORTRAIT]\n" + "\n".join(logs)
    except Exception as e:
        return f"[ERROR LIVEPORTRAIT] {e}"


def run_fase_subtitulos(proyecto_id: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido."
    try:
        sub_engine = SubtitleEngine(storage, proyecto_id)
        res = sub_engine.generar_subtitulos_timeline_completo()
        return f"[EXITO SUBTITULOS]\nPistas generadas:\n- {res['normal'].name}\n- {res['highlights'].name}\n- {res['en'].name}"
    except Exception as e:
        return f"[ERROR SUBTITULOS] {e}"


def run_fase_assembly(proyecto_id: str, nombre_out: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido.", None
    try:
        nombre = nombre_out.strip() if nombre_out else "pelicula_completa.mp4"
        if not nombre.endswith(".mp4"):
            nombre += ".mp4"
        assembly = AssemblyEngine(proyecto_id, storage)
        out = assembly.ensamblar_pelicula(nombre_salida=nombre)
        return f"[EXITO ENSAMBLAJE] Pelicula exportada: {out.name}", str(out)
    except Exception as e:
        return f"[ERROR ENSAMBLAJE] {e}", None


def run_pipeline_completo(proyecto_id: str, voz_sel: str, voz_manual: str):
    if not proyecto_id or proyecto_id == "(Sin proyectos)":
        return "[AVISO] Seleccione un proyecto valido.", None
    logs = ["=== INICIANDO PIPELINE AUTOMATIZADO COMPLETO ==="]
    try:
        voz = resolver_voz_seleccionada(voz_sel, voz_manual)

        logs.append("[1/7] Cargando Guion...")
        gm = GuionManager(storage, proyecto_id)
        gm.cargar_guion_desde_json()
        config = storage.cargar_config(proyecto_id)
        logs.append(f"[OK] Guion procesado: {len(config.get('escenas', []))} escenas.")

        logs.append(f"[2/7] Generando Audio TTS (Voz: {voz or 'Predefinida en Guion'})...")
        tts = TTSEngine(storage, proyecto_id)
        for esc in config.get("escenas", []):
            tts.procesar_escena(esc["id"], voz_override=voz)
        logs.append("[OK] Pistas de audio completadas.")

        logs.append("[3/7] Renderizando Imagenes HD (SDXL)...")
        img_engine = ImageEngine(storage, api_client, proyecto_id)
        for p_id, p_data in config.get("personajes", {}).items():
            img_engine.asegurar_imagen_maestra_personaje(p_id, p_data)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                img_engine.renderizar_escena_personaje(esc["id"])
            elif esc.get("tipo") == "b_roll":
                img_engine.renderizar_escena_broll(esc["id"])
        logs.append("[OK] Imagenes generadas.")

        logs.append("[4/7] Generando Driving Videos (SadTalker)...")
        api_client.liberar_memoria()
        sadtalker = SadTalkerEngine(proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                p_id = esc.get("personaje_id")
                avatar = config.get("personajes", {}).get(p_id, {}).get("avatar") or "man.png"
                sadtalker.generar_video_borrador(e_id, avatar, f"{e_id}.wav")
        logs.append("[OK] Driving videos listos.")

        logs.append("[5/7] Animando escenas B-Roll (SVD + RIFE)...")
        broll = BRollAnimationEngine(storage, api_client, proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "b_roll":
                broll.animar_escena_broll(esc["id"])
        logs.append("[OK] B-Roll animado.")

        logs.append("[6/7] Procesando LivePortrait HD y Masterizado...")
        vid_engine = VideoEngine(storage, api_client, proyecto_id)
        for esc in config.get("escenas", []):
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                vid_engine.renderizar_lipsync(e_id, f"{e_id}_personaje_00001_.png", f"{e_id}_driving.mp4")
        logs.append("[OK] LivePortrait masterizado.")

        logs.append("[7/7] Generando Pistas SRT Maestras...")
        sub_engine = SubtitleEngine(storage, proyecto_id)
        sub_engine.generar_subtitulos_timeline_completo()
        logs.append("[OK] Subtitulos generados.")

        logs.append("[FINAL] Ensamblando Pelicula Completa...")
        assembly = AssemblyEngine(proyecto_id, storage)
        out = assembly.ensamblar_pelicula(nombre_salida="pelicula_completa.mp4")
        logs.append(f"\n[COMPLETADO] Pelicula generada exitosamente: {out.name}")
        return "\n".join(logs), str(out)
    except Exception as e:
        logs.append(f"\n[ERROR EN PIPELINE] {e}")
        return "\n".join(logs), None


# ========================================================
# CONSTRUCCION DE INTERFAZ GRADIO (DISENO PROFESIONAL Y LIMPIO)
# ========================================================

with gr.Blocks(title="Orquestador de Video IA - Studio Web") as demo:
    gr.Markdown("""
    # Orquestador de Video IA — Studio Web
    **Pipeline Automatizado HD:** ComfyUI | Kokoro TTS | SadTalker | LivePortrait | DaVinci SRT
    """)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### Configuracion del Proyecto")
                dropdown_proyectos = gr.Dropdown(
                    label="Proyecto Activo",
                    choices=obtener_proyectos(),
                    value=obtener_proyectos()[0] if obtener_proyectos() else "(Sin proyectos)"
                )
                btn_recargar_proyectos = gr.Button("Actualizar Proyectos", size="sm")

            with gr.Group():
                gr.Markdown("### Configuracion de Audio (Kokoro-82M)")
                dropdown_voz = gr.Dropdown(
                    label="Voz para Sintesis",
                    choices=VOCES_CHOICES,
                    value="(Usar del guion)",
                    info="Sobreescribe la voz para todas las escenas o respeta las del guion."
                )
                input_voz_manual = gr.Textbox(
                    label="Formula de Mezcla (Opcional)",
                    placeholder="ej: em_alex:0.7+am_fenrir:0.3",
                    info="Voice Blending ponderado (tiene prioridad sobre la lista)."
                )

        with gr.Column(scale=2):
            dashboard_md = gr.Markdown("Cargando metricas...")
            video_preview = gr.Video(label="Previsualizacion de Video Final", interactive=False)

    with gr.Tabs():
        with gr.TabItem("Pipeline Automatizado"):
            gr.Markdown("Ejecucion secuencial de Fases 1 a 8 con asignacion automatica de recursos.")
            btn_run_all = gr.Button("Ejecutar Pipeline Completo", variant="primary", size="lg")
            log_all = gr.Textbox(label="Consola de Procesamiento", lines=12, max_lines=25)

        with gr.TabItem("Control por Fases"):
            gr.Markdown("Ejecucion independiente por etapas para ajuste, depuracion o reintento de escenas.")
            with gr.Row():
                btn_fase1 = gr.Button("1. Cargar Guion", size="sm")
                btn_fase2 = gr.Button("2. Sintesis TTS", size="sm")
                btn_fase3 = gr.Button("3. Render Imagenes", size="sm")
            with gr.Row():
                btn_fase4 = gr.Button("4. Driving SadTalker", size="sm")
                btn_fase4b = gr.Button("5. Animacion B-Roll", size="sm")
                btn_fase5 = gr.Button("6. LivePortrait HD", size="sm")
            with gr.Row():
                btn_fase6 = gr.Button("7. Subtitulos SRT", size="sm")
                btn_fase7 = gr.Button("8. Ensamblar Video", size="sm")

            input_nombre_ensamble = gr.Textbox(label="Archivo de Salida MP4", value="pelicula_completa.mp4")
            log_fases = gr.Textbox(label="Registro de Actividad", lines=8)

    # Eventos
    def refrescar_todo(p_id):
        res, guion, vid = obtener_estado_proyecto(p_id)
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

    btn_run_all.click(
        run_pipeline_completo,
        inputs=[dropdown_proyectos, dropdown_voz, input_voz_manual],
        outputs=[log_all, video_preview]
    ).then(
        refrescar_todo,
        inputs=[dropdown_proyectos],
        outputs=[dashboard_md, video_preview]
    )

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

    demo.load(
        refrescar_todo,
        inputs=[dropdown_proyectos],
        outputs=[dashboard_md, video_preview]
    )

if __name__ == "__main__":
    puerto = 7860
    print(f"\n[INFO] Iniciando Interfaz Web en http://127.0.0.1:{puerto} ...")
    demo.launch(server_name="127.0.0.1", server_port=puerto, inbrowser=True)
