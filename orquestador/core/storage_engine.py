import json
import shutil
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR, PRESETS_DIR


class StorageEngine:
    """
    Motor de persistencia y gestión de configuraciones, presets y plantillas de proyecto.
    """

    # Prompt negativo estructural inquebrantable (Reglas estrictas de LivePortrait, Encuadre y Penumbra)
    PROMPT_NEGATIVO_ESTRUCTURAL = (
        "multiple people, 2people, two men, group, crowd, extra persons, duplicate, clone, "
        "full body, long shot, wide shot, distant view, legs, feet, shoes, lower body, "
        "open mouth, parted lips, visible teeth, tongue, smiling, laughing, screaming, grimacing, "
        "tilted head, looking away, looking up, looking down, low angle, high angle, side view, profile, back view, "
        "hands on face, touching face, "
        "pitch black eye sockets, pure black facial silhouette, shadows completely concealing mouth, obscured lip contour, "
        "blurry background, heavy bokeh, extreme depth of field, out of focus background, smudged details, "
        "deformed eyes, crossed eyes, bad facial anatomy, mutated face, elongated chin, stretched forehead, extra limbs, low resolution, artifacts"
    )

    ESTILOS_PRESETS = {
        "analog_horror": {
            "nombre": "Terror Psicológico / Found Footage (Flash Frontal)",
            "estilo_global": (
                "raw found footage still, police bodycam flashlight illumination, harsh direct on-camera flash, "
                "stark frontal lighting with completely shadowless flat facial features, unsettling cold stoic gaze, "
                "sickly pale desaturated waxy skin tone, dark under-eye pigmentation, analog VHS sensor grain, "
                "suffocating pitch black surrounding darkness in background, disturbing psychological horror realism"
            ),
            "prompt_negativo_global": (
                "bright ambient lighting, studio softbox, 3d cartoon, 3d pixar, videogame render, unreal engine, "
                "octane render, smooth plastic skin, glamorous makeup, smiling, happy, open mouth, teeth, warm golden hour, "
                "vibrant colors, sunlight, female, woman, girl, "
                f"{PROMPT_NEGATIVO_ESTRUCTURAL}"
            ),
        },
        "stylized_3d_animation": {
            "nombre": "Animación 3D Estilizada (CGI Alta Gama)",
            "estilo_global": (
                "cinematic 3D animation film render, high-end stylized 3D CGI, smooth 3D character sculpture, "
                "clean subsurface scattering, soft studio key lighting, rich stylized textures, sharp background in focus, "
                "polished 3D movie aesthetic, neutral dramatic color grading"
            ),
            "prompt_negativo_global": f"photorealistic, raw photo, photograph, real human face, skin pores, realistic wrinkles, blemishes, 2d, flat drawing, anime lineart, sketch, painting, oil painting, watercolor, low poly, {PROMPT_NEGATIVO_ESTRUCTURAL}",
        },
        "corporate_thriller": {
            "nombre": "Thriller Corporativo Realista",
            "estilo_global": (
                "cinematic film still from a realistic corporate thriller film, sharp 35mm photography, "
                "executive office and boardroom interior lighting, elegant dark polished wood and glass architectural textures, "
                "natural window daylight, deep focus across the scene, sober high-end film color palette, "
                "classic tailored business wardrobe"
            ),
            "prompt_negativo_global": f"cyberpunk, sci-fi, neon, glowing, techwear, anime, cartoon, 3d render, painting, drawing, plastic skin, {PROMPT_NEGATIVO_ESTRUCTURAL}",
        },
    }

    def __init__(self):
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def listar_proyectos(self) -> list[str]:
        if not INPUT_DIR.exists():
            return []
        return sorted([d.name for d in INPUT_DIR.iterdir() if d.is_dir() and (d / "project_config.json").exists()])

    def crear_proyecto(self, nombre_id: str, preset_key: str, estilo_global: str, prompt_negativo_global: str) -> dict:
        proj_input_dir = INPUT_DIR / nombre_id
        proj_output_dir = OUTPUT_DIR / nombre_id

        if proj_input_dir.exists():
            raise FileExistsError(f"El proyecto '{nombre_id}' ya existe en ComfyUI/input.")

        templates_dir = proj_input_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        (proj_input_dir / "audios").mkdir(parents=True, exist_ok=True)
        (proj_input_dir / "ref_images").mkdir(parents=True, exist_ok=True)
        (proj_input_dir / "driving").mkdir(parents=True, exist_ok=True)

        (proj_output_dir / "ref_images").mkdir(parents=True, exist_ok=True)
        (proj_output_dir / "sadtalker_temp").mkdir(parents=True, exist_ok=True)
        (proj_output_dir / "renders").mkdir(parents=True, exist_ok=True)
        (proj_output_dir / "subtitles").mkdir(parents=True, exist_ok=True)
        (proj_output_dir / "final").mkdir(parents=True, exist_ok=True)

        if PRESETS_DIR.exists():
            for json_file in PRESETS_DIR.glob("*.json"):
                shutil.copy2(json_file, templates_dir / json_file.name)

            preset_src_dir = PRESETS_DIR / preset_key
            if preset_src_dir.exists() and preset_src_dir.is_dir():
                for json_file in preset_src_dir.glob("*.json"):
                    shutil.copy2(json_file, templates_dir / json_file.name)

        config = {
            "id_proyecto": nombre_id,
            "preset_usado": preset_key,
            "estilo_global": estilo_global,
            "prompt_negativo_global": prompt_negativo_global,
            "personajes": {},
            "escenas": [],
        }

        self.guardar_config(nombre_id, config)
        return config

    def cargar_config(self, nombre_id: str) -> dict:
        config_path = INPUT_DIR / nombre_id / "project_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Configuración no encontrada para el proyecto '{nombre_id}' en: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def guardar_config(self, nombre_id: str, config: dict):
        config_path = INPUT_DIR / nombre_id / "project_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def obtener_plantilla(self, nombre_id: str, nombre_plantilla: str) -> dict:
        ruta_template = INPUT_DIR / nombre_id / "templates" / nombre_plantilla
        if ruta_template.exists():
            with open(ruta_template, "r", encoding="utf-8") as f:
                return json.load(f)

        ruta_global = PRESETS_DIR / nombre_plantilla
        if ruta_global.exists():
            with open(ruta_global, "r", encoding="utf-8") as f:
                return json.load(f)

        raise FileNotFoundError(
            f"Plantilla '{nombre_plantilla}' no encontrada en el proyecto '{nombre_id}' "
            f"ni en el directorio global de presets ({PRESETS_DIR})."
        )