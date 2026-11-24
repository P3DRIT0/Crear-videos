"""Contratos HOME aislados. El servidor WORK no importa estos clientes."""
import hashlib
import http.client
import json
import re
import socket
from threading import Event, Thread
from urllib.parse import urlencode
from uuid import UUID

from packages.contracts.production import Script


class LocalAPI:
    def __init__(self, profile, port, timeout=15):
        if profile not in ("home16","home32"):
            raise ValueError("El perfil WORK bloquea los proveedores de inferencia.")
        self.port=port
        self.timeout=timeout

    def request(self,path,body=None,binary=False,allow_empty=False,cancelled=None):
        if cancelled and cancelled():
            raise RuntimeError("Cancelación local solicitada.")
        conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=self.timeout)
        stop=Event()
        monitor=None
        if cancelled:
            def watch():
                while not stop.wait(0.25):
                    if cancelled():
                        try:
                            if conn.sock:
                                conn.sock.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        conn.close()
                        return
            monitor=Thread(target=watch,daemon=True)
            monitor.start()
        try:
            conn.request("POST" if body is not None else "GET",path,
                         body=json.dumps(body) if body is not None else None,
                         headers={"Content-Type":"application/json"})
            resp=conn.getresponse()
            if resp.status!=200:
                raise RuntimeError(f"El proveedor local devolvió HTTP {resp.status}.")
            data=resp.read(16*1024*1024+1)
            if len(data)>16*1024*1024:
                raise ValueError("El proveedor excedió el límite del resultado.")
            expected=resp.getheader("Content-Length")
            if expected is not None and int(expected)!=len(data):
                raise RuntimeError("Respuesta incompleta del proveedor local.")
            if allow_empty and not data:
                return None
            return data if binary else json.loads(data)
        except http.client.HTTPException as exc:
            raise RuntimeError("Respuesta incompleta del proveedor local: "+type(exc).__name__) from exc
        finally:
            stop.set()
            if monitor:
                monitor.join(timeout=2)
            conn.close()


class Ollama(LocalAPI):
    def __init__(self, profile, port=11434):
        super().__init__(profile,port,timeout=90)

    def script(self, model, digest, idea, cancelled=None):
        if not re.fullmatch(r"[a-zA-Z0-9._/-]+:[a-zA-Z0-9._-]+",model) or "cloud" in model.lower():
            raise ValueError("Se requiere un tag local explícito.")
        if not re.fullmatch("[0-9a-f]{64}",digest):
            raise ValueError("Digest de modelo inválido.")
        installed=self.request("/api/tags").get("models",[])
        if not any(m.get("name")==model and m.get("digest")==digest for m in installed):
            raise ValueError("El modelo y su digest deben estar instalados y verificados en HOME.")
        result=self.request("/api/chat",{"model":model,"messages":[
            {"role":"system","content":"Devuelve solo el JSON solicitado: version=1, hook, scenes y cta. Exactamente cinco escenas. Cada texto, incluidos hook y cta, debe tener como máximo 80 caracteres. Una frase corta por escena, sin diálogos. No añadas campos."},
            {"role":"user","content":idea[:1000]}],
            "stream":False,"format":Script.model_json_schema(),"keep_alive":0,
            **({"think": False} if model.startswith("qwen3:") else {}),
            "options":{"temperature":0,"num_ctx":2048,"num_predict":512}}, cancelled=cancelled)
        return Script.model_validate_json(result["message"]["content"])


class ComfyUI(LocalAPI):
    def __init__(self,profile,port=8188):
        super().__init__(profile,port)

    def submit(self,workflow,checksum,prompt_id=None):
        if hashlib.sha256(workflow).hexdigest()!=checksum:
            raise ValueError("El workflow ha cambiado desde su revisión.")
        graph=json.loads(workflow)
        if not isinstance(graph,dict) or not 1<=len(graph)<=64:
            raise ValueError("Grafo inválido.")
        # Solo nodos nativos contemplados en el contrato local.
        allowed={"EmptyImage","SaveImage","CheckpointLoaderSimple","CLIPTextEncode","KSampler",
                 "EmptyLatentImage","VAEDecode","CLIPLoader","UNETLoader","VAELoader",
                 "ModelSamplingSD3","Wan22ImageToVideoLatent","CreateVideo","SaveVideo","LoadImage"}
        if any(node.get("class_type") not in allowed for node in graph.values()):
            raise ValueError("El grafo contiene nodos sin auditar.")
        body={"prompt":graph}
        if prompt_id is not None:
            body["prompt_id"]=str(UUID(prompt_id))
        result=self.request("/prompt",body)
        result_id=str(UUID(result["prompt_id"]))
        if prompt_id is not None and result_id != prompt_id:
            raise RuntimeError("ComfyUI no respetó el ID persistido; reconciliar antes de continuar.")
        return result_id

    def status(self,job):
        job=str(UUID(job))
        return self.request("/history/"+job).get(job)

    def collect(self,history,extension):
        if extension not in (".png",".mp4"):
            raise ValueError("Formato no soportado.")
        if history["status"]["status_str"]!="success":
            raise ValueError("La ejecución no terminó correctamente.")
        for node in history["outputs"].values():
            for img in node.get("images",[]):
                if img["type"]!="output" or img.get("subfolder") or not re.fullmatch(r"[\w .-]+",img["filename"]):
                    raise ValueError("Se esperaba un nombre de salida local.")
                if not img["filename"].lower().endswith(extension):
                    continue
                return self.request("/view?"+urlencode({"filename":img["filename"],"type":"output"}),binary=True)
        raise ValueError("El workflow no devolvió un archivo del tipo previsto.")

    def cancel_queued(self,job):
        return self.request("/queue",{"delete":[str(UUID(job))]},allow_empty=True)

    def cancel(self,job):
        job=str(UUID(job))
        self.cancel_queued(job)
        return self.request("/interrupt",{"prompt_id":job},allow_empty=True)

    def cancel_atomic(self,job):
        return self.request("/api/jobs/"+str(UUID(job))+"/cancel",{})
