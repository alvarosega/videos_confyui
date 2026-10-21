import json
from pathlib import Path
from config import INPUT_DIR
from core.storage_engine import StorageEngine


class GuionManager:
    def __init__(self, storage_engine: StorageEngine, proyecto_id: str):
        self.storage = storage_engine
        self.proyecto_id = proyecto_id
        self.project_dir = INPUT_DIR / proyecto_id

    def cargar_guion_desde_json(self, ruta_json: Path | str = None):
        """
        Carga el archivo guion.json y persiste en project_config.json:
        estilo_global, prompt_negativo_global, personajes y escenas (con prompt_negativo_escena).
        """
        if ruta_json is None:
            path_guion = self.project_dir / "guion.json"
            if not path_guion.exists():
                path_guion = Path("guion.json")
        else:
            path_guion = Path(ruta_json)

        if not path_guion.exists():
            raise FileNotFoundError(f"No se encontró el archivo de guion en: {path_guion.resolve()}")

        with open(path_guion, "r", encoding="utf-8") as f:
            datos = json.load(f)

        config = self.storage.cargar_config(self.proyecto_id)

        # Actualizar estilos globales si existen en el guion
        if "estilo_global" in datos:
            config["estilo_global"] = datos["estilo_global"]
        if "prompt_negativo_global" in datos:
            config["prompt_negativo_global"] = datos["prompt_negativo_global"]

        # Actualizar entidades y escenas completas
        config["personajes"] = datos.get("personajes", {})
        config["escenas"] = datos.get("escenas", [])

        self.storage.guardar_config(self.proyecto_id, config)
        print(f"[ÉXITO] Guion cargado: {len(config['personajes'])} personajes y {len(config['escenas'])} escenas registradas.")