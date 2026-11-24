"""Contratos HOME aislados. El servidor WORK no importa estos clientes."""
import hashlib
import http.client
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from uuid import UUID

from packages.contracts.production import Script


class LocalAPI:
    def __init__(self, profile, port, timeout=15):
        if profile not in ("home16","home32"):
            raise ValueError("El perfil WORK bloquea los proveedores de inferencia.")
        self.port=port
        self.timeout=timeout

    def request(self,path,body=None,binary=False,allow_empty=False):
        conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=self.timeout)
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
            if allow_empty and not data:
                return None
            return data if binary else json.loads(data)
        finally:
            conn.close()


class Ollama(LocalAPI):
    def __init__(self, profile, port=11434):
        super().__init__(profile,port,timeout=90)

    def script(self, model, digest, idea):
        if not re.fullmatch(r"[a-zA-Z0-9._/-]+:[a-zA-Z0-9._-]+",model) or "cloud" in model.lower():
            raise ValueError("Se requiere un tag local explícito.")
        if not re.fullmatch("[0-9a-f]{64}",digest):
            raise ValueError("Digest de modelo inválido.")
        installed=self.request("/api/tags").get("models",[])
        if not any(m.get("name")==model and m.get("digest")==digest for m in installed):
            raise ValueError("El modelo y su digest deben estar instalados y verificados en HOME.")
        result=self.request("/api/chat",{"model":model,"messages":[{"role":"user","content":idea[:1000]}],
            "stream":False,"format":Script.model_json_schema(),"keep_alive":0,
            "options":{"temperature":0,"num_predict":512}})
        return Script.model_validate_json(result["message"]["content"])


class ComfyUI(LocalAPI):
    def __init__(self,profile,port=8188):
        super().__init__(profile,port)

    def submit(self,workflow,checksum):
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
        result=self.request("/prompt",{"prompt":graph})
        return str(UUID(result["prompt_id"]))

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
