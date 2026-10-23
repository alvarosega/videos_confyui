import os
import sys
import winsound
from pathlib import Path

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

# Habilitar soporte de secuencias de escape ANSI nativas en consolas Windows
os.system("")


class UI:
    """Utilidades de interfaz visual, colores y ergonomía para la terminal."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    CHECK = f"\033[92m[✓]{RESET}"
    WARN = f"\033[93m[!]{RESET}"
    EMPTY = f"\033[90m[ ]{RESET}"
    ARROW = f"\033[96m➜{RESET}"

    @staticmethod
    def limpiar():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def pausa():
        input(f"\n{UI.GRAY}  Presione Enter para continuar...{UI.RESET}")

    @staticmethod
    def exito(msg: str):
        print(f" {UI.GREEN}✓ {msg}{UI.RESET}")

    @staticmethod
    def error(msg: str):
        print(f" {UI.RED}✗ {msg}{UI.RESET}")

    @staticmethod
    def aviso(msg: str):
        print(f" {UI.YELLOW}▲ {msg}{UI.RESET}")

    @staticmethod
    def info(msg: str):
        print(f" {UI.CYAN}ℹ {msg}{UI.RESET}")


class OrchestratorCLI:
    def __init__(self):
        self.storage = StorageEngine()
        self.api_client = ComfyAPIClient()
        self.proyecto_activo = None
        self.config_activa = None

    def _emitir_alerta_sonora(self, exito: bool = True):
        try:
            if exito:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass

    def _obtener_resumen_estado(self) -> dict:
        """Audita el disco en tiempo real para generar el dashboard del proyecto activo."""
        if not self.proyecto_activo or not self.config_activa:
            return {}

        input_dir = INPUT_DIR / self.proyecto_activo
        output_dir = OUTPUT_DIR / self.proyecto_activo

        escenas = self.config_activa.get("escenas", [])
        personajes = self.config_activa.get("personajes", {})

        escenas_p = [e for e in escenas if e.get("tipo") == "personaje"]
        escenas_b = [e for e in escenas if e.get("tipo") == "b_roll"]

        # 1. Guion
        guion_ok = bool(escenas)

        # 2. Audios TTS
        audios_dir = input_dir / "audios"
        audios_listos = sum(1 for e in escenas if (audios_dir / f"{e['id']}.wav").exists())

        # 3. Imágenes Maestras y de Escena
        ref_in = input_dir / "ref_images"
        ref_out = output_dir / "ref_images"
        masters_listos = sum(
            1 for p_id in personajes
            if (ref_in / f"master_{p_id}.png").exists() or (ref_out / f"master_{p_id}.png").exists()
        )
        imgs_p_listas = sum(
            1 for e in escenas_p
            if list(ref_in.glob(f"{e['id']}_personaje*.png")) or list(ref_out.glob(f"{e['id']}_personaje*.png"))
        )
        imgs_b_listas = sum(
            1 for e in escenas_b
            if list(ref_in.glob(f"{e['id']}_b_roll*.png")) or list(ref_out.glob(f"{e['id']}_b_roll*.png")) or
               list(ref_in.glob(f"{e['id']}_broll*.png")) or list(ref_out.glob(f"{e['id']}_broll*.png"))
        )

        # 4. SadTalker Driving
        sadtalker_dir = output_dir / "sadtalker_temp"
        driving_listos = sum(1 for e in escenas_p if (sadtalker_dir / f"{e['id']}_driving.mp4").exists())

        # 4b. Animación B-Roll (SVD)
        renders_dir = output_dir / "renders"
        broll_listos = sum(1 for e in escenas_b if (renders_dir / f"{e['id']}_final.mp4").exists())

        # 5. LivePortrait HD
        lp_listos = sum(
            1 for e in escenas_p
            if (renders_dir / f"{e['id']}_enhanced.mp4").exists() or (renders_dir / f"{e['id']}_final.mp4").exists()
        )

        # 6. Subtítulos SRT
        sub_dir = output_dir / "subtitles"
        sub_ok = (sub_dir / f"{self.proyecto_activo}_normal.srt").exists()

        # 7. Película final
        final_dir = output_dir / "final"
        pelicula_file = None
        if final_dir.exists():
            candidatos = list(final_dir.glob("*.mp4"))
            if candidatos:
                pelicula_file = candidatos[0]

        return {
            "total_escenas": len(escenas),
            "total_personajes": len(personajes),
            "escenas_p": len(escenas_p),
            "escenas_b": len(escenas_b),
            "guion_ok": guion_ok,
            "audios_ok": audios_listos,
            "masters_ok": masters_listos,
            "imgs_escenas_ok": imgs_p_listas + imgs_b_listas,
            "driving_ok": driving_listos,
            "broll_ok": broll_listos,
            "lp_ok": lp_listos,
            "sub_ok": sub_ok,
            "pelicula": pelicula_file
        }

    def _imprimir_dashboard(self):
        """Imprime la tarjeta visual de estado del proyecto activo."""
        estado = self._obtener_resumen_estado()
        if not estado:
            return

        total = estado["total_escenas"]
        total_p = estado["escenas_p"]
        total_b = estado["escenas_b"]
        total_pers = estado["total_personajes"]

        preset_nombre = self.config_activa.get("preset_usado", "Personalizado")
        estilo_corto = self.config_activa.get("estilo_global", "")[:50] + "..." if self.config_activa.get("estilo_global") else "N/A"

        print(f"\n{UI.BOLD}┌─ ESTADO EN TIEMPO REAL: {UI.CYAN}{self.proyecto_activo}{UI.RESET} {UI.GRAY}(Preset: {preset_nombre}){UI.RESET}")
        print(f"{UI.BOLD}│{UI.RESET} {UI.GRAY}Estilo:{UI.RESET} {estilo_corto}")
        print(f"{UI.BOLD}├─────────────────────────────────────────────────────────────────────────────{UI.RESET}")

        # 1. Guion
        tag1 = UI.CHECK if estado["guion_ok"] else UI.EMPTY
        print(f"{UI.BOLD}│{UI.RESET} {tag1} 1. Guion Narrativo    : {total} escenas ({total_p} personajes, {total_b} B-Roll) | {total_pers} entidades")

        # 2. Audios
        tag2 = UI.CHECK if (total > 0 and estado["audios_ok"] == total) else (UI.WARN if estado["audios_ok"] > 0 else UI.EMPTY)
        print(f"{UI.BOLD}│{UI.RESET} {tag2} 2. Audios TTS (Kokoro) : {estado['audios_ok']}/{total} pistas WAV generadas con metadata JSON")

        # 3. Imágenes
        imgs_totales = estado["imgs_escenas_ok"]
        tag3 = UI.CHECK if (total > 0 and imgs_totales == total and estado['masters_ok'] == total_pers) else (UI.WARN if imgs_totales > 0 else UI.EMPTY)
        print(f"{UI.BOLD}│{UI.RESET} {tag3} 3. Imágenes HD (SDXL)  : {estado['masters_ok']}/{total_pers} Masters OK | {imgs_totales}/{total} escenas generadas")

        # 4. SadTalker
        tag4 = UI.CHECK if (total_p > 0 and estado["driving_ok"] == total_p) else (UI.WARN if estado["driving_ok"] > 0 else UI.EMPTY)
        print(f"{UI.BOLD}│{UI.RESET} {tag4} 4. SadTalker Driving   : {estado['driving_ok']}/{total_p} videos driving 1:1 generados")

        # 4b. B-Roll
        tag4b = UI.CHECK if (total_b > 0 and estado["broll_ok"] == total_b) else (UI.WARN if estado["broll_ok"] > 0 else (UI.GRAY + "[—]" + UI.RESET if total_b == 0 else UI.EMPTY))
        desc_b = f"{estado['broll_ok']}/{total_b} clips animados SVD" if total_b > 0 else "No aplica (sin escenas B-Roll)"
        print(f"{UI.BOLD}│{UI.RESET} {tag4b} 5. Animación B-Roll    : {desc_b}")

        # 5. LivePortrait HD
        tag5 = UI.CHECK if (total_p > 0 and estado["lp_ok"] == total_p) else (UI.WARN if estado["lp_ok"] > 0 else UI.EMPTY)
        print(f"{UI.BOLD}│{UI.RESET} {tag5} 6. LivePortrait HD     : {estado['lp_ok']}/{total_p} renders masterizados en alta definición")

        # 6. Subtítulos
        tag6 = UI.CHECK if estado["sub_ok"] else UI.EMPTY
        desc_sub = "Normal, Highlights y EN exportados para DaVinci" if estado["sub_ok"] else "Pendiente de exportación"
        print(f"{UI.BOLD}│{UI.RESET} {tag6} 7. Subtítulos SRT      : {desc_sub}")

        # 7. Película final
        pelicula = estado["pelicula"]
        if pelicula:
            peso_mb = round(pelicula.stat().st_size / (1024 * 1024), 1)
            tag7 = UI.CHECK
            desc_pel = f"{pelicula.name} ({peso_mb} MB) disponible en /final"
        else:
            tag7 = UI.EMPTY
            desc_pel = "Pendiente de ensamblaje"
        print(f"{UI.BOLD}│{UI.RESET} {tag7} 8. Película Completa   : {desc_pel}")

        print(f"{UI.BOLD}└─────────────────────────────────────────────────────────────────────────────{UI.RESET}")

    def _seleccionar_elementos(self, items: list, label_fn, titulo: str) -> list:
        """Selector interactivo con soporte de rangos (1-5), listas (1,3) o todo (T)."""
        if not items:
            UI.aviso(f"No hay elementos disponibles para {titulo.lower()}.")
            return []

        print(f"\n{UI.BOLD}{UI.CYAN}--- SELECCIÓN: {titulo.upper()} ---{UI.RESET}")
        for idx, item in enumerate(items, 1):
            print(f"  {UI.BOLD}[{idx:2d}]{UI.RESET} {label_fn(item)}")

        print(f"\n  {UI.GREEN}[T]{UI.RESET} Procesar TODAS ({len(items)})    {UI.GRAY}[0 / V]{UI.RESET} Cancelar y volver")
        sel = input(f"\n{UI.ARROW} Ingrese selección (ej: '1', '1,3', '1-5' o 'T'): ").strip()

        if not sel or sel.upper() in ["0", "V", "VOLVER", "CANCELAR", "SALIR"]:
            return []

        if sel.upper() in ["T", "TODAS", "ALL", "*"]:
            return items

        indices = set()
        partes = [p.strip() for p in sel.split(",") if p.strip()]

        for parte in partes:
            if "-" in parte:
                subpartes = parte.split("-")
                if len(subpartes) == 2 and subpartes[0].isdigit() and subpartes[1].isdigit():
                    inicio = int(subpartes[0])
                    fin = int(subpartes[1])
                    for i in range(min(inicio, fin), max(inicio, fin) + 1):
                        if 1 <= i <= len(items):
                            indices.add(i - 1)
            elif parte.isdigit():
                val = int(parte)
                if 1 <= val <= len(items):
                    indices.add(val - 1)

        seleccionados = [items[i] for i in sorted(indices)]
        if not seleccionados:
            UI.error("Selección vacía o inválida.")
        else:
            print(f"{UI.GRAY}  -> {len(seleccionados)} elemento(s) seleccionado(s).{UI.RESET}")
        return seleccionados

    def iniciar(self):
        while True:
            UI.limpiar()
            print(f"\n{UI.BOLD}{UI.CYAN}==============================================================================={UI.RESET}")
            print(f"{UI.BOLD}{UI.WHITE}           ORQUESTADOR DE VIDEO IA - PIPELINE MODULAR HD (COMFYUI)            {UI.RESET}")
            print(f"{UI.BOLD}{UI.CYAN}==============================================================================={UI.RESET}")

            if not self.proyecto_activo:
                print(f"\n  {UI.BOLD}[1]{UI.RESET} 📁 Cargar Proyecto Existente")
                print(f"  {UI.BOLD}[2]{UI.RESET} ➕ Crear Nuevo Proyecto")
                print(f"  {UI.BOLD}[3]{UI.RESET} 🚪 Salir")

                opcion = input(f"\n{UI.ARROW} Seleccione una opción: ").strip()

                if opcion == "1":
                    self.menu_cargar_proyecto()
                elif opcion == "2":
                    self.menu_crear_proyecto()
                elif opcion in ["3", "q", "Q", "exit"]:
                    sys.exit(0)
                else:
                    UI.error("Opción inválida.")
                    UI.pausa()
            else:
                self._imprimir_dashboard()

                print(f"\n{UI.BOLD}ACCIONES DISPONIBLES:{UI.RESET}")
                print(f"  {UI.BOLD}[1]{UI.RESET} 📝 Registrar / Recargar Guion JSON      {UI.BOLD}[5]{UI.RESET} 🎬 Animación B-Roll (SVD + RIFE)")
                print(f"  {UI.BOLD}[2]{UI.RESET} 🎙️ Generar Audios TTS (Kokoro-82M)       {UI.BOLD}[6]{UI.RESET} 👄 Renderizar LivePortrait HD")
                print(f"  {UI.BOLD}[3]{UI.RESET} 🎨 Renderizar Imágenes HD (SDXL)         {UI.BOLD}[7]{UI.RESET} 💬 Generar Subtítulos SRT")
                print(f"  {UI.BOLD}[4]{UI.RESET} 🎭 Driving Video Morfométrica (SadTalker){UI.BOLD}[8]{UI.RESET} 🎞️ Ensamblar Película Completa")
                print(f"\n  {UI.GREEN}{UI.BOLD}[9]{UI.RESET} ⚡ {UI.GREEN}{UI.BOLD}EJECUTAR PIPELINE COMPLETO AUTOMATIZADO (Fases 1 a 8){UI.RESET}")
                print(f"  {UI.GRAY}[0] 🔄 Cambiar de Proyecto                  [S] 🚪 Salir{UI.RESET}")

                opcion = input(f"\n{UI.ARROW} Seleccione una opción: ").strip().lower()

                if opcion == "1":
                    self.fase_1_guion()
                elif opcion == "2":
                    self.fase_2_tts()
                elif opcion == "3":
                    self.fase_3_imagenes()
                elif opcion == "4":
                    self.fase_4_sadtalker()
                elif opcion == "5":
                    self.fase_4b_broll_animation()
                elif opcion == "6":
                    self.fase_5_liveportrait()
                elif opcion == "7":
                    self.fase_6_subtitulos()
                elif opcion == "8":
                    self.fase_7_ensamblaje()
                elif opcion == "9":
                    self.ejecutar_pipeline_automatico()
                elif opcion in ["0", "v", "volver", "cambiar"]:
                    self.proyecto_activo = None
                    self.config_activa = None
                elif opcion in ["s", "salir", "q"]:
                    sys.exit(0)
                else:
                    UI.error("Opción inválida.")
                    UI.pausa()

    def menu_crear_proyecto(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}--- CREACIÓN DE NUEVO PROYECTO ---{UI.RESET}")
        nombre = input(f"{UI.ARROW} ID/Nombre del proyecto (ej: 021_nuevo_video): ").strip()
        if not nombre:
            UI.error("El nombre no puede estar vacío.")
            UI.pausa()
            return

        presets = list(self.storage.ESTILOS_PRESETS.items())
        print(f"\n{UI.BOLD}Presets de estilo visual disponibles:{UI.RESET}")
        for idx, (k, v) in enumerate(presets, 1):
            print(f"  {UI.BOLD}[{idx}]{UI.RESET} {UI.CYAN}{k}{UI.RESET}: {v['nombre']}")

        sel = input(f"\n{UI.ARROW} Seleccione el número de preset base (Enter para [1]): ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(presets):
            preset_key, preset_data = presets[int(sel) - 1]
            estilo = preset_data["estilo_global"]
            negativo = preset_data["prompt_negativo_global"]
        else:
            default_key, default_data = presets[0]
            preset_key = default_key
            estilo = default_data["estilo_global"]
            negativo = default_data["prompt_negativo_global"]

        try:
            self.config_activa = self.storage.crear_proyecto(nombre, preset_key, estilo, negativo)
            self.proyecto_activo = nombre
            UI.exito(f"Proyecto '{nombre}' inicializado exitosamente.")
            self._emitir_alerta_sonora(exito=True)
        except Exception as e:
            UI.error(f"No se pudo crear el proyecto: {e}")
            self._emitir_alerta_sonora(exito=False)
        UI.pausa()

    def menu_cargar_proyecto(self):
        UI.limpiar()
        proyectos = self.storage.listar_proyectos()
        if not proyectos:
            UI.aviso("No se encontraron proyectos configurados en ComfyUI/input/projects.")
            UI.pausa()
            return

        print(f"\n{UI.BOLD}{UI.CYAN}--- SELECCIONAR PROYECTO EXISTENTE ---{UI.RESET}\n")

        # Presentación tabular en columnas compactas
        num_cols = 2
        for i in range(0, len(proyectos), num_cols):
            fila = proyectos[i:i + num_cols]
            textos_col = [f"  {UI.BOLD}[{i + j + 1:2d}]{UI.RESET} {fila[j]:<32}" for j in range(len(fila))]
            print("".join(textos_col))

        print(f"\n  {UI.GRAY}[0 / V] Cancelar y volver al menú principal{UI.RESET}")
        sel = input(f"\n{UI.ARROW} Ingrese el número o escriba el nombre del proyecto: ").strip()

        if not sel or sel.upper() in ["0", "V", "VOLVER"]:
            return

        nombre_elegido = None
        if sel.isdigit():
            idx = int(sel)
            if 1 <= idx <= len(proyectos):
                nombre_elegido = proyectos[idx - 1]
        elif sel in proyectos:
            nombre_elegido = sel
        else:
            # Búsqueda parcial por si escribió parte del nombre (ej: "019")
            coincidencias = [p for p in proyectos if sel.lower() in p.lower()]
            if len(coincidencias) == 1:
                nombre_elegido = coincidencias[0]

        if nombre_elegido:
            try:
                self.config_activa = self.storage.cargar_config(nombre_elegido)
                self.proyecto_activo = nombre_elegido
                UI.exito(f"Proyecto '{nombre_elegido}' cargado.")
            except Exception as e:
                UI.error(f"Error al cargar configuración: {e}")
                UI.pausa()
        else:
            UI.error("Proyecto no encontrado.")
            UI.pausa()

    def fase_1_guion(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 1: REGISTRAR GUION Y ESCENAS ==={UI.RESET}")
        gm = GuionManager(self.storage, self.proyecto_activo)

        print(f"\n  {UI.BOLD}[1]{UI.RESET} Cargar guion.json automático del proyecto {UI.GRAY}(Recomendado){UI.RESET}")
        print(f"  {UI.BOLD}[2]{UI.RESET} Cancelar y volver")

        sub = input(f"\n{UI.ARROW} Seleccione opción (1-2): ").strip()
        if sub == "1":
            try:
                gm.cargar_guion_desde_json()
                self.config_activa = self.storage.cargar_config(self.proyecto_activo)
                UI.exito("Guion cargado y sincronizado con project_config.json.")
                self._emitir_alerta_sonora(exito=True)
            except Exception as e:
                UI.error(f"Fallo al cargar guion: {e}")
                self._emitir_alerta_sonora(exito=False)
            UI.pausa()

    def fase_2_tts(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 2: GENERACIÓN DE VOCES TTS (KOKORO-82M) ==={UI.RESET}")
        tts = TTSEngine(self.storage, self.proyecto_activo)
        escenas = self.config_activa.get("escenas", [])
        if not escenas:
            UI.aviso("No hay escenas registradas. Ejecute la Fase 1 primero.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas,
            lambda e: f"{e['id']} ({e.get('tipo', 'escena')}) - \"{e.get('dialogo', '')[:40]}...\"",
            "Generar Audio TTS"
        )

        if not escenas_sel:
            return

        print(f"\n{UI.BOLD}Procesando {len(escenas_sel)} pistas de audio:{UI.RESET}")
        exitos = 0
        for esc in escenas_sel:
            try:
                arch, dur = tts.procesar_escena(esc["id"])
                if arch:
                    UI.exito(f"Escena {esc['id']}: OK ({arch.name}, {dur:.2f}s)")
                    exitos += 1
            except Exception as e:
                UI.error(f"Escena {esc['id']}: {e}")

        self._emitir_alerta_sonora(exito=(exitos > 0))
        UI.pausa()

    def fase_3_imagenes(self):
        img_engine = ImageEngine(self.storage, self.api_client, self.proyecto_activo)

        while True:
            UI.limpiar()
            print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 3: RENDERIZADO DE IMÁGENES HD (SDXL + IP-ADAPTER) ==={UI.RESET}")
            print(f"  {UI.BOLD}[1]{UI.RESET} Generar / Actualizar Imágenes Maestras de Personaje (Portraits)")
            print(f"  {UI.BOLD}[2]{UI.RESET} Renderizar Escenas de Personaje (Trasplante Facial + ControlNet)")
            print(f"  {UI.BOLD}[3]{UI.RESET} Renderizar Escenas B-Roll (Entornos y Fondos)")
            print(f"  {UI.GRAY}[0 / V] Volver al menú principal{UI.RESET}")

            op = input(f"\n{UI.ARROW} Seleccione una opción: ").strip()

            if op == "1":
                self._menu_maestras(img_engine)
            elif op == "2":
                self._menu_personajes_individual(img_engine)
            elif op == "3":
                self._menu_broll(img_engine)
            elif op in ["0", "v", "V", "volver"]:
                break
            else:
                UI.error("Opción inválida.")
                UI.pausa()

    def _menu_maestras(self, img_engine):
        UI.limpiar()
        personajes = self.config_activa.get("personajes", {})
        if not personajes:
            UI.aviso("No hay personajes registrados en la configuración.")
            UI.pausa()
            return

        p_items = list(personajes.items())
        seleccionados = self._seleccionar_elementos(
            p_items,
            lambda p: f"{p[0]} (Nombre: {p[1].get('nombre', p[0])})",
            "Imágenes Maestras de Personaje"
        )

        for p_id, p_data in seleccionados:
            try:
                img_engine.asegurar_imagen_maestra_personaje(p_id, p_data, forzar_regeneracion=True)
                UI.exito(f"Master {p_id} generada y almacenada.")
            except Exception as e:
                UI.error(f"Fallo en Master {p_id}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def _menu_personajes_individual(self, img_engine):
        UI.limpiar()
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]
        if not escenas_p:
            UI.aviso("No hay escenas de tipo personaje en este guion.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p,
            lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')}) - \"{e.get('accion_prompt', '')[:35]}...\"",
            "Escenas de Personaje"
        )

        for esc in escenas_sel:
            try:
                img_engine.renderizar_escena_personaje(esc["id"])
                UI.exito(f"Escena {esc['id']} renderizada.")
            except Exception as e:
                UI.error(f"Fallo en {esc['id']}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def _menu_broll(self, img_engine):
        UI.limpiar()
        escenas_broll = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "b_roll"]
        if not escenas_broll:
            UI.aviso("No hay escenas de tipo B-Roll en este guion.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_broll,
            lambda e: f"{e['id']} (B-Roll) - \"{e.get('accion_prompt', '')[:35]}...\"",
            "Escenas B-Roll"
        )

        for esc in escenas_sel:
            try:
                img_engine.renderizar_escena_broll(esc["id"])
                UI.exito(f"Escena B-Roll {esc['id']} renderizada.")
            except Exception as e:
                UI.error(f"Fallo en B-Roll {esc['id']}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def fase_4_sadtalker(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 4: VIDEO DRIVING MORFOMÉTRICO (SADTALKER) ==={UI.RESET}")
        # Optimización proactiva de VRAM
        self.api_client.liberar_memoria()

        sadtalker = SadTalkerEngine(self.proyecto_activo)
        personajes = self.config_activa.get("personajes", {})
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]

        if not escenas_p:
            UI.aviso("No hay escenas de personaje para generar driving videos.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p,
            lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')})",
            "Generar Driving Video (SadTalker)"
        )

        for esc in escenas_sel:
            e_id = esc["id"]
            p_id = esc.get("personaje_id")
            p_data = personajes.get(p_id, {})
            avatar = p_data.get("avatar") or "man.png"
            aud_name = f"{e_id}.wav"

            try:
                driving_path = sadtalker.generar_video_borrador(e_id, avatar, aud_name)
                UI.exito(f"Driving listo para {e_id}: {driving_path.name}")
            except Exception as e:
                UI.error(f"SadTalker en {e_id}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def fase_4b_broll_animation(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 4B: ANIMACIÓN CINEMATOGRÁFICA B-ROLL (SVD + RIFE) ==={UI.RESET}")
        broll_engine = BRollAnimationEngine(self.storage, self.api_client, self.proyecto_activo)
        escenas_broll = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "b_roll"]

        if not escenas_broll:
            UI.aviso("No hay escenas B-Roll registradas.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_broll,
            lambda e: f"{e['id']} (B-Roll)",
            "Animación B-Roll"
        )

        for esc in escenas_sel:
            e_id = esc["id"]
            try:
                broll_engine.animar_escena_broll(e_id)
                UI.exito(f"Animación completada para {e_id}.")
            except Exception as e:
                UI.error(f"Animación en {e_id}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def fase_5_liveportrait(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 5: RENDERIZADO LIVEPORTRAIT HD + MASTERIZADO ==={UI.RESET}")
        vid_engine = VideoEngine(self.storage, self.api_client, self.proyecto_activo)
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]

        if not escenas_p:
            UI.aviso("No hay escenas de personaje registradas.")
            UI.pausa()
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p,
            lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')})",
            "Renderizar LivePortrait HD"
        )

        for esc in escenas_sel:
            e_id = esc["id"]
            img_name = f"{e_id}_personaje_00001_.png"
            driving_video_name = f"{e_id}_driving.mp4"

            try:
                exito, p_id = vid_engine.renderizar_lipsync(e_id, img_name, driving_video_name)
                UI.exito(f"LivePortrait HD masterizado para {e_id} (Prompt ID: {p_id})")
            except Exception as e:
                UI.error(f"LivePortrait en {e_id}: {e}")

        self._emitir_alerta_sonora(exito=True)
        UI.pausa()

    def fase_6_subtitulos(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 6: SUBTÍTULOS SRT PROFESIONALES (DAVINCI RESOLVE) ==={UI.RESET}")
        sub_engine = SubtitleEngine(self.storage, self.proyecto_activo)
        escenas = self.config_activa.get("escenas", [])

        if not escenas:
            UI.aviso("No hay escenas registradas.")
            UI.pausa()
            return

        print(f"  {UI.BOLD}[1]{UI.RESET} Generar Timeline Maestro (.SRT Completo Acumulado)")
        print(f"  {UI.BOLD}[2]{UI.RESET} Generar Subtítulos Individuales por Escena")
        print(f"  {UI.GRAY}[0 / V] Volver al menú principal{UI.RESET}")

        op = input(f"\n{UI.ARROW} Seleccione una opción: ").strip()

        if op == "1":
            try:
                sub_engine.generar_subtitulos_timeline_completo()
                UI.exito("Pistas SRT maestras exportadas con éxito.")
                self._emitir_alerta_sonora(exito=True)
            except Exception as e:
                UI.error(f"Fallo al generar timeline SRT: {e}")
                self._emitir_alerta_sonora(exito=False)
            UI.pausa()
        elif op == "2":
            escenas_sel = self._seleccionar_elementos(
                escenas,
                lambda e: f"{e['id']} - \"{e.get('dialogo', '')[:35]}...\"",
                "Generar SRT Individual"
            )
            for esc in escenas_sel:
                try:
                    sub_engine.generar_subtitulos_escena(esc["id"])
                    UI.exito(f"SRT individual listo para {esc['id']}.")
                except Exception as e:
                    UI.error(f"Fallo en {esc['id']}: {e}")
            self._emitir_alerta_sonora(exito=True)
            UI.pausa()

    def fase_7_ensamblaje(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.CYAN}=== FASE 7: ENSAMBLAJE FINAL DE PELÍCULA MP4 ==={UI.RESET}")
        assembly = AssemblyEngine(self.proyecto_activo, self.storage)
        try:
            nombre = input(f"{UI.ARROW} Nombre del video final (Enter para 'pelicula_completa.mp4'): ").strip()
            if not nombre:
                nombre = "pelicula_completa.mp4"
            if not nombre.endswith(".mp4"):
                nombre += ".mp4"

            salida = assembly.ensamblar_pelicula(nombre_salida=nombre)
            UI.exito(f"Película ensamblada: {salida.resolve()}")
            self._emitir_alerta_sonora(exito=True)
        except Exception as e:
            UI.error(f"Fallo en ensamblaje: {e}")
            self._emitir_alerta_sonora(exito=False)
        UI.pausa()

    def ejecutar_pipeline_automatico(self):
        UI.limpiar()
        print(f"\n{UI.BOLD}{UI.GREEN}==============================================================================={UI.RESET}")
        print(f"{UI.BOLD}{UI.GREEN}       INICIANDO PIPELINE AUTOMATIZADO COMPLETO: {self.proyecto_activo}        {UI.RESET}")
        print(f"{UI.BOLD}{UI.GREEN}==============================================================================={UI.RESET}")

        # 1. Guion
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 1/7] Carga y Validación de Guion ---{UI.RESET}")
        gm = GuionManager(self.storage, self.proyecto_activo)
        try:
            gm.cargar_guion_desde_json()
            self.config_activa = self.storage.cargar_config(self.proyecto_activo)
            UI.exito("Guion validado y sincronizado.")
        except Exception as e:
            UI.error(f"Fallo en Fase 1: {e}")
            UI.pausa()
            return

        # 2. TTS
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 2/7] Síntesis de Voz TTS (Kokoro-82M) ---{UI.RESET}")
        tts = TTSEngine(self.storage, self.proyecto_activo)
        for esc in self.config_activa.get("escenas", []):
            try:
                tts.procesar_escena(esc["id"])
                UI.exito(f"Audio listo: {esc['id']}.wav")
            except Exception as e:
                UI.error(f"TTS {esc['id']}: {e}")

        # 3. Imágenes HD
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 3/7] Renderizado de Imágenes HD (SDXL) ---{UI.RESET}")
        img_engine = ImageEngine(self.storage, self.api_client, self.proyecto_activo)
        personajes = self.config_activa.get("personajes", {})
        escenas = self.config_activa.get("escenas", [])

        for p_id, p_data in personajes.items():
            try:
                img_engine.asegurar_imagen_maestra_personaje(p_id, p_data, forzar_regeneracion=False)
                UI.exito(f"Master OK: {p_id}")
            except Exception as e:
                UI.error(f"Master {p_id}: {e}")

        for esc in escenas:
            e_id = esc["id"]
            try:
                if esc.get("tipo") == "personaje":
                    img_engine.renderizar_escena_personaje(e_id)
                    UI.exito(f"Imagen escena personaje: {e_id}")
                elif esc.get("tipo") == "b_roll":
                    img_engine.renderizar_escena_broll(e_id)
                    UI.exito(f"Imagen escena B-Roll: {e_id}")
            except Exception as e:
                UI.error(f"Imagen {e_id}: {e}")

        # Optimización de VRAM
        print(f"\n{UI.GRAY}[Optimización GPU] Liberando VRAM de ComfyUI para SadTalker...{UI.RESET}")
        self.api_client.liberar_memoria()

        # 4. SadTalker
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 4/7] Video Driving SadTalker ---{UI.RESET}")
        sadtalker = SadTalkerEngine(self.proyecto_activo)
        for esc in escenas:
            e_id = esc["id"]
            if esc.get("tipo") == "personaje":
                p_id = esc.get("personaje_id")
                p_data = personajes.get(p_id, {})
                avatar = p_data.get("avatar") or "man.png"
                aud_name = f"{e_id}.wav"
                try:
                    sadtalker.generar_video_borrador(e_id, avatar, aud_name)
                    UI.exito(f"Driving SadTalker listo: {e_id}")
                except Exception as e:
                    UI.error(f"SadTalker {e_id}: {e}")

        # 4b. B-Roll SVD
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 5/7] Animación B-Roll SVD + RIFE ---{UI.RESET}")
        broll_engine = BRollAnimationEngine(self.storage, self.api_client, self.proyecto_activo)
        for esc in escenas:
            if esc.get("tipo") == "b_roll":
                e_id = esc["id"]
                try:
                    broll_engine.animar_escena_broll(e_id)
                    UI.exito(f"B-Roll animado: {e_id}")
                except Exception as e:
                    UI.error(f"B-Roll {e_id}: {e}")

        # 5. LivePortrait HD
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 6/7] LivePortrait HD Lipsync + Enhancer ---{UI.RESET}")
        vid_engine = VideoEngine(self.storage, self.api_client, self.proyecto_activo)
        for esc in escenas:
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                img_name = f"{e_id}_personaje_00001_.png"
                driving_video_name = f"{e_id}_driving.mp4"
                try:
                    vid_engine.renderizar_lipsync(e_id, img_name, driving_video_name)
                    UI.exito(f"LivePortrait masterizado: {e_id}")
                except Exception as e:
                    UI.error(f"LivePortrait {e_id}: {e}")

        # 6. Subtítulos
        print(f"\n{UI.BOLD}{UI.CYAN}--- [AUTO 7/7] Pistas SRT Maestras (DaVinci Resolve) ---{UI.RESET}")
        sub_engine = SubtitleEngine(self.storage, self.proyecto_activo)
        try:
            sub_engine.generar_subtitulos_timeline_completo()
            UI.exito("Subtítulos generados con éxito.")
        except Exception as e:
            UI.error(f"Subtítulos: {e}")

        # 7. Ensamblaje
        print(f"\n{UI.BOLD}{UI.CYAN}--- [FINAL] Ensamblado de Película Completa ---{UI.RESET}")
        assembly = AssemblyEngine(self.proyecto_activo, self.storage)
        try:
            assembly.ensamblar_pelicula(nombre_salida="pelicula_completa.mp4")
            UI.exito("Película final exportada.")
        except Exception as e:
            UI.aviso(f"Ensamblado automático: {e}")

        print(f"\n{UI.BOLD}{UI.GREEN}==============================================================================={UI.RESET}")
        print(f"{UI.BOLD}{UI.GREEN}              PIPELINE AUTOMATIZADO FINALIZADO CON ÉXITO                       {UI.RESET}")
        print(f"{UI.BOLD}{UI.GREEN}==============================================================================={UI.RESET}")
        self._emitir_alerta_sonora(exito=True)
        UI.pausa()


if __name__ == "__main__":
    app = OrchestratorCLI()
    app.iniciar()
