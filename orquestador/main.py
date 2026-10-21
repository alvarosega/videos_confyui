import sys
import winsound
from pathlib import Path

from core.storage_engine import StorageEngine
from core.comfy_client import ComfyAPIClient
from modules.guion_manager import GuionManager
from modules.tts_engine import TTSEngine
from modules.image_engine import ImageEngine
from modules.video_engine import VideoEngine
from modules.broll_engine import BRollAnimationEngine
from modules.sadtalker_engine import SadTalkerEngine
from modules.subtitle_engine import SubtitleEngine


class OrchestratorCLI:
    def _emitir_alerta_sonora(self, exito: bool = True):
        """Emite un sonido de notificación del sistema según el resultado."""
        try:
            if exito:
                # Sonido de notificación de Windows (Beep positivo)
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                # Sonido de error del sistema
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass
    def __init__(self):
        self.storage = StorageEngine()
        self.api_client = ComfyAPIClient()
        self.proyecto_activo = None
        self.config_activa = None

    def _seleccionar_elementos(self, items: list, label_fn, titulo: str) -> list:
        if not items:
            print(f"[INFO] No hay elementos disponibles para {titulo.lower()}.")
            return []

        print(f"\n-- {titulo.upper()} --")
        for idx, item in enumerate(items, 1):
            print(f"{idx}. {label_fn(item)}")
        print(f"{len(items) + 1}. Procesar TODAS")

        sel = input(f"\nSeleccione (ej: '1', '1,3', o '{len(items)+1}' / 'T' para TODAS): ").strip()
        if not sel:
            return []

        if sel.upper() in ["T", "TODAS", "ALL"] or sel == str(len(items) + 1):
            return items

        seleccionados = []
        for parte in sel.split(","):
            p = parte.strip()
            if p.isdigit():
                idx = int(p)
                if 1 <= idx <= len(items):
                    item = items[idx - 1]
                    if item not in seleccionados:
                        seleccionados.append(item)

        if not seleccionados:
            print("[ERROR] Selección inválida.")
        return seleccionados

    def iniciar(self):
        while True:
            print("\n" + "=" * 50)
            print(" ORQUESTADOR DE VIDEO IA - CLI MODULAR")
            print("=" * 50)
            if self.proyecto_activo:
                print(f"Proyecto actual: [{self.proyecto_activo}]")
                print("1. Fase 1: Registrar Personaje / Escena (Guion)")
                print("2. Fase 2: Generar Audios TTS (Kokoro)")
                print("3. Fase 3: Renderizar Imágenes HD (Native SDXL)")
                print("4. Fase 4: Generar Video Driving Borrador (SadTalker CLI)")
                print("5. Fase 4b: Animación Cinematográfica B-Roll (SVD / ComfyUI)")
                print("6. Fase 5: Renderizar LivePortrait HD (ComfyUI)")
                print("7. Fase 6: Generar Subtítulos SRT (DaVinci Resolve)")
                print("8. EJECUTAR PIPELINE AUTOMATIZADO (Fases 1 a 6)")
                print("9. Cambiar / Cerrar Proyecto Activo")
                print("10. Salir")
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
                    self.ejecutar_pipeline_automatico()
                elif opcion == "9":
                    self.proyecto_activo = None
                    self.config_activa = None
                elif opcion == "10":
                    sys.exit(0)
                else:
                    print("[ERROR] Opción inválida.")

    def menu_crear_proyecto(self):
        nombre = input("ID/Nombre del proyecto (ej: 03_video_herencia): ").strip()
        if not nombre:
            print("[ERROR] Nombre vacío.")
            return

        presets = list(self.storage.ESTILOS_PRESETS.items())
        print("\nPresets disponibles:")
        for idx, (k, v) in enumerate(presets, 1):
            print(f"{idx}. {k}: {v['nombre']}")

        sel = input("Seleccione el número del preset base: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(presets):
            preset_key, preset_data = presets[int(sel) - 1]
            estilo = preset_data["estilo_global"]
            negativo = preset_data["prompt_negativo_global"]
        else:
            print("[ERROR] Selección inválida. Se aplicará 'dark_concept' por defecto.")
            preset_key = "dark_concept"
            estilo = self.storage.ESTILOS_PRESETS["dark_concept"]["estilo_global"]
            negativo = self.storage.ESTILOS_PRESETS["dark_concept"]["prompt_negativo_global"]

        try:
            self.config_activa = self.storage.crear_proyecto(nombre, preset_key, estilo, negativo)
            self.proyecto_activo = nombre
            print(f"\n[ÉXITO] Proyecto '{nombre}' inicializado.")
        except Exception as e:
            print(f"[ERROR] No se pudo crear el proyecto: {e}")

    def menu_cargar_proyecto(self):
        proyectos = self.storage.listar_proyectos()
        if not proyectos:
            print("[INFO] No se encontraron proyectos.")
            return

        print("\nProyectos existentes:")
        for idx, p in enumerate(proyectos, 1):
            print(f"{idx}. {p}")

        sel = input("Seleccione el número de proyecto: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(proyectos):
            nombre = proyectos[int(sel) - 1]
            try:
                self.config_activa = self.storage.cargar_config(nombre)
                self.proyecto_activo = nombre
                print(f"[ÉXITO] Proyecto '{nombre}' cargado.")
            except Exception as e:
                print(f"[ERROR] {e}")
        else:
            print("[ERROR] Selección inválida.")

    def fase_1_guion(self):
        gm = GuionManager(self.storage, self.proyecto_activo)
        print("\n--- FASE 1: GUION ---")
        print("1. Cargar 'guion.json' automático (Recomendado)")
        print("2. Volver al menú principal")
        sub = input("Seleccione opción (1-2): ").strip()

        if sub == "1":
            try:
                gm.cargar_guion_desde_json()
            except Exception as e:
                print(f"[ERROR]: {e}")

        self.config_activa = self.storage.cargar_config(self.proyecto_activo)
        self._emitir_alerta_sonora(exito=True)

    def fase_2_tts(self):
        tts = TTSEngine(self.storage, self.proyecto_activo)
        escenas = self.config_activa.get("escenas", [])
        if not escenas:
            print("[INFO] No hay escenas registradas en el guion.")
            return

        escenas_sel = self._seleccionar_elementos(
            escenas,
            lambda e: f"{e['id']} ({e.get('tipo')}) - \"{e.get('dialogo', '')[:35]}...\"",
            "Generar Audio TTS para Escenas",
        )

        for escena in escenas_sel:
            try:
                arch, dur = tts.procesar_escena(escena["id"])
                if arch:
                    print(f"-> Escena {escena['id']}: OK ({arch}, {dur}s)")
            except Exception as e:
                print(f"[ERROR en {escena['id']}]: {e}")
        self._emitir_alerta_sonora(exito=True)

    def fase_3_imagenes(self):
        img_engine = ImageEngine(self.storage, self.api_client, self.proyecto_activo)

        while True:
            print("\n--- FASE 3: RENDERIZADO DE IMÁGENES ---")
            print("1. Gestionar Imágenes Maestras (Personajes)")
            print("2. Renderizar Escenas de Personaje (SDXL)")
            print("3. Renderizar Escenas B-Roll (Entorno)")
            print("4. Volver al menú principal")

            op = input("Seleccione una opción (1-4): ").strip()

            if op == "1":
                self._menu_maestras(img_engine)
            elif op == "2":
                self._menu_personajes_individual(img_engine)
            elif op == "3":
                self._menu_broll(img_engine)
            elif op == "4":
                break
            else:
                print("[ERROR] Opción inválida.")
        self._emitir_alerta_sonora(exito=True)

    def _menu_maestras(self, img_engine):
        personajes = self.config_activa.get("personajes", {})
        if not personajes:
            print("[ERROR] No hay personajes registrados.")
            return

        p_items = list(personajes.items())
        seleccionados = self._seleccionar_elementos(
            p_items,
            lambda p: f"{p[0]} (Nombre: {p[1].get('nombre', p[0])})",
            "Imágenes Maestras de Personaje",
        )

        for p_id, p_data in seleccionados:
            try:
                img_engine.asegurar_imagen_maestra_personaje(p_id, p_data, forzar_regeneracion=True)
            except Exception as e:
                print(f"[ERROR en {p_id}]: {e}")
        self._emitir_alerta_sonora(exito=True)
    def _menu_personajes_individual(self, img_engine):
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]
        if not escenas_p:
            print("[INFO] No hay escenas de personajes.")
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p, lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')})", "Escenas de Personaje"
        )

        for esc in escenas_sel:
            try:
                img_engine.renderizar_escena_personaje(esc["id"])
            except Exception as e:
                print(f"[ERROR en {esc['id']}]: {e}")
        self._emitir_alerta_sonora(exito=True)

    def _menu_broll(self, img_engine):
        escenas_broll = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "b_roll"]
        if not escenas_broll:
            print("[INFO] No hay escenas B-Roll.")
            return

        escenas_sel = self._seleccionar_elementos(escenas_broll, lambda e: f"{e['id']} (B-Roll)", "Escenas B-Roll")

        for esc in escenas_sel:
            try:
                img_engine.renderizar_escena_broll(esc["id"])
            except Exception as e:
                print(f"[ERROR en {esc['id']}]: {e}")
        self._emitir_alerta_sonora(exito=True)
    def fase_4_sadtalker(self):
        sadtalker = SadTalkerEngine(self.proyecto_activo)
        personajes = self.config_activa.get("personajes", {})
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]

        if not escenas_p:
            print("[INFO] No hay escenas de personaje registradas para SadTalker.")
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p,
            lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')})",
            "Generar Driving Video (SadTalker)",
        )

        for escena in escenas_sel:
            e_id = escena["id"]
            p_id = escena.get("personaje_id")
            p_data = personajes.get(p_id, {})
            avatar = p_data.get("avatar") or "man.png"
            aud_name = f"{e_id}.wav"

            try:
                driving_path = sadtalker.generar_video_borrador(e_id, avatar, aud_name)
                print(f"-> Driving video generado para {e_id}: {driving_path.name}")
            except Exception as e:
                print(f"[ERROR SadTalker {e_id}]: {e}")
        self._emitir_alerta_sonora(exito=True)

    def fase_4b_broll_animation(self):
        broll_engine = BRollAnimationEngine(self.storage, self.api_client, self.proyecto_activo)
        escenas_broll = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "b_roll"]

        if not escenas_broll:
            print("[INFO] No hay escenas B-Roll registradas.")
            return

        escenas_sel = self._seleccionar_elementos(escenas_broll, lambda e: f"{e['id']} (B-Roll)", "Animación SVD B-Roll")

        for esc in escenas_sel:
            e_id = esc["id"]
            try:
                broll_engine.animar_escena_broll(e_id)
            except Exception as e:
                print(f"[ERROR en {e_id}]: {e}")
        self._emitir_alerta_sonora(exito=True)

    def fase_5_liveportrait(self):
        vid_engine = VideoEngine(self.storage, self.api_client, self.proyecto_activo)
        escenas_p = [e for e in self.config_activa.get("escenas", []) if e.get("tipo") == "personaje"]

        if not escenas_p:
            print("[INFO] No hay escenas de personaje registradas para LivePortrait.")
            return

        escenas_sel = self._seleccionar_elementos(
            escenas_p,
            lambda e: f"{e['id']} (Personaje: {e.get('personaje_id')})",
            "Renderizar LivePortrait HD",
        )

        for escena in escenas_sel:
            e_id = escena["id"]
            img_name = f"{e_id}_personaje_00001_.png"
            driving_video_name = f"{e_id}_driving.mp4"

            try:
                exito, p_id = vid_engine.renderizar_lipsync(e_id, img_name, driving_video_name)
                print(f"-> LivePortrait HD completado para {e_id} (Prompt ID: {p_id})")
            except Exception as e:
                print(f"[ERROR LivePortrait {e_id}]: {e}")
        self._emitir_alerta_sonora(exito=True)

    def fase_6_subtitulos(self):
        sub_engine = SubtitleEngine(self.storage, self.proyecto_activo)
        escenas = self.config_activa.get("escenas", [])

        if not escenas:
            print("[INFO] No hay escenas registradas para generar subtítulos.")
            return

        while True:
            print("\n--- FASE 6: SUBTÍTULOS SRT (DAVINCI RESOLVE) ---")
            print("1. Generar Timeline Maestro (.SRT Completo Acumulado)")
            print("2. Generar Subtítulos Individuales por Escena")
            print("3. Volver al menú principal")

            op = input("Seleccione una opción (1-3): ").strip()

            if op == "1":
                try:
                    sub_engine.generar_subtitulos_timeline_completo()
                except Exception as e:
                    print(f"[ERROR generando timeline SRT]: {e}")
            elif op == "2":
                escenas_sel = self._seleccionar_elementos(
                    escenas,
                    lambda e: f"{e['id']} - \"{e.get('dialogo', '')[:35]}...\"",
                    "Generar SRT Individual",
                )
                for esc in escenas_sel:
                    try:
                        sub_engine.generar_subtitulos_escena(esc["id"])
                    except Exception as e:
                        print(f"[ERROR en {esc['id']}]: {e}")
            elif op == "3":
                break
            else:
                print("[ERROR] Opción inválida.")
        self._emitir_alerta_sonora(exito=True)

    def ejecutar_pipeline_automatico(self):
        print("\n" + "=" * 60)
        print(f" INICIANDO PIPELINE AUTOMATIZADO (FASES 1 A 6): {self.proyecto_activo}")
        print("=" * 60)

        # FASE 1: Carga de guion
        print("\n--- [AUTO 1/6] Carga de Guion JSON ---")
        gm = GuionManager(self.storage, self.proyecto_activo)
        try:
            gm.cargar_guion_desde_json()
            self.config_activa = self.storage.cargar_config(self.proyecto_activo)
        except Exception as e:
            print(f"[ERROR FASE 1]: {e}")
            return

        # FASE 2: Audio TTS
        print("\n--- [AUTO 2/6] Generación de Audios TTS ---")
        tts = TTSEngine(self.storage, self.proyecto_activo)
        for esc in self.config_activa.get("escenas", []):
            try:
                tts.procesar_escena(esc["id"])
            except Exception as e:
                print(f"[ERROR TTS {esc['id']}]: {e}")

        # FASE 3: Renderizado de Imágenes HD
        print("\n--- [AUTO 3/6] Renderizado de Imágenes HD (SDXL) ---")
        img_engine = ImageEngine(self.storage, self.api_client, self.proyecto_activo)
        personajes = self.config_activa.get("personajes", {})
        escenas = self.config_activa.get("escenas", [])

        for p_id, p_data in personajes.items():
            try:
                img_engine.asegurar_imagen_maestra_personaje(p_id, p_data, forzar_regeneracion=False)
            except Exception as e:
                print(f"[ERROR Master {p_id}]: {e}")

        for esc in escenas:
            e_id = esc["id"]
            tipo = esc.get("tipo")
            try:
                if tipo == "personaje":
                    img_engine.renderizar_escena_personaje(e_id)
                elif tipo == "b_roll":
                    img_engine.renderizar_escena_broll(e_id)
            except Exception as e:
                print(f"[ERROR Imagen {e_id}]: {e}")

        # FASE 4: SadTalker CLI
        print("\n--- [AUTO 4/6] Generación Video Driving (SadTalker) ---")
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
                except Exception as e:
                    print(f"[ERROR SadTalker {e_id}]: {e}")

        # FASE 4b: Animación B-Roll (SVD)
        print("\n--- [AUTO 4b/6] Animación B-Roll (SVD) ---")
        broll_engine = BRollAnimationEngine(self.storage, self.api_client, self.proyecto_activo)
        for esc in escenas:
            if esc.get("tipo") == "b_roll":
                e_id = esc["id"]
                try:
                    broll_engine.animar_escena_broll(e_id)
                except Exception as e:
                    print(f"[ERROR Animación B-Roll {e_id}]: {e}")

        # FASE 5: LivePortrait HD
        print("\n--- [AUTO 5/6] LivePortrait HD (ComfyUI) ---")
        vid_engine = VideoEngine(self.storage, self.api_client, self.proyecto_activo)
        for esc in escenas:
            if esc.get("tipo") == "personaje":
                e_id = esc["id"]
                img_name = f"{e_id}_personaje_00001_.png"
                driving_video_name = f"{e_id}_driving.mp4"
                try:
                    vid_engine.renderizar_lipsync(e_id, img_name, driving_video_name)
                except Exception as e:
                    print(f"[ERROR LivePortrait {e_id}]: {e}")

        # FASE 6: Generación de Subtítulos SRT
        print("\n--- [AUTO 6/6] Generación de Subtítulos SRT ---")
        sub_engine = SubtitleEngine(self.storage, self.proyecto_activo)
        try:
            sub_engine.generar_subtitulos_timeline_completo()
        except Exception as e:
            print(f"[ERROR Subtítulos Timeline]: {e}")

        print("\n" + "=" * 60)
        print(" PIPELINE AUTOMATIZADO COMPLETO (FASES 1 A 6 FINALIZADAS)")
        print("=" * 60)
        self._emitir_alerta_sonora(exito=True)

if __name__ == "__main__":
    app = OrchestratorCLI()
    app.iniciar()