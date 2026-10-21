import json
import uuid
import urllib.request
import urllib.error
import websocket
from config import COMFYUI_SERVER_URL


class ComfyAPIClient:
    def __init__(self, server_address: str = COMFYUI_SERVER_URL):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

    def _conectar_ws(self) -> websocket.WebSocket:
        ws_url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        return ws

    def enviar_prompt(self, workflow_dict: dict) -> str:
        """Envía el workflow a la cola de ComfyUI y retorna el prompt_id."""
        url = f"http://{self.server_address}/prompt"
        payload = json.dumps({
            "prompt": workflow_dict,
            "client_id": self.client_id
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                if "prompt_id" not in res:
                    raise RuntimeError(f"Respuesta inválida de ComfyUI: {res}")
                return res["prompt_id"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"ComfyUI rechazó el workflow (HTTP {e.code}):\n{error_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"No se pudo conectar con ComfyUI en {self.server_address}: {e}")
    def ejecutar_workflow(self, workflow_dict: dict, timeout: int = 600) -> tuple[str, list[dict]]:
        """
        Envía el prompt y escucha por WebSocket hasta que finalice la ejecución.
        Retorna una tupla (prompt_id, archivos_generados).
        Soporta outputs de imagen (SaveImage) y video (VHS_VideoCombine).
        """
        ws = self._conectar_ws()
        prompt_id = self.enviar_prompt(workflow_dict)
        archivos_generados = []

        ws.settimeout(timeout)
        try:
            while True:
                mensaje_raw = ws.recv()
                if isinstance(mensaje_raw, str):
                    evento = json.loads(mensaje_raw)
                    tipo = evento.get("type")
                    data = evento.get("data", {})

                    if tipo == "execution_error":
                        if data.get("prompt_id") == prompt_id:
                            msg = data.get("exception_message")
                            node_id = data.get("node_id")
                            raise RuntimeError(f"Error en nodo {node_id}: {msg}")

                    elif tipo == "executed":
                        if data.get("prompt_id") == prompt_id:
                            output_data = data.get("output", {})
                            # Captura SaveImage estándar
                            if "images" in output_data:
                                archivos_generados.extend(output_data["images"])
                            # Captura VHS_VideoCombine (videos / gifs)
                            if "gifs" in output_data:
                                archivos_generados.extend(output_data["gifs"])
                            if "videos" in output_data:
                                archivos_generados.extend(output_data["videos"])

                    elif tipo == "executing":
                        if data.get("prompt_id") == prompt_id and data.get("node") is None:
                            break
        except websocket.WebSocketTimeoutException:
            raise TimeoutError(f"Timeout ({timeout}s) esperando a ComfyUI para el prompt '{prompt_id}'.")
        finally:
            ws.close()

        return prompt_id, archivos_generados