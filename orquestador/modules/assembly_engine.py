import os
import subprocess
from config import OUTPUT_DIR

class AssemblyEngine:
    """Módulo para la Fase 5: Ensamblaje final de la película"""
    def __init__(self, proyecto_id):
        self.proyecto_id = proyecto_id
        self.renders_dir = OUTPUT_DIR / proyecto_id / "renders"
        self.final_dir = OUTPUT_DIR / proyecto_id / "final"

    def ensamblar_pelicula(self, nombre_salida="pelicula_final.mp4"):
        archivos_mp4 = sorted([f for f in self.renders_dir.glob("*_final.mp4")])
        if not archivos_mp4:
            raise FileNotFoundError("No se encontraron clips en la carpeta de renders para ensamblar.")

        lista_txt = self.renders_dir / "lista_concat.txt"
        with open(lista_txt, "w", encoding="utf-8") as f:
            for archivo in archivos_mp4:
                f.write(f"file '{archivo.name}'\n")

        ruta_out = self.final_dir / nombre_salida
        
        comando = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_txt),
            "-c", "copy",
            str(ruta_out)
        ]
        
        subprocess.run(comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(lista_txt)
        
        print(f"[ENSAMBLAJE] Película exportada con éxito en: {ruta_out}")
        return ruta_out