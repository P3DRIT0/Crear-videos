"""Checkpoint HOME en SQL. Solo inferencia local, sin descargas ni fallback."""
import hashlib
import json
import logging
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from integrations.home import gpu, used_ram, verified_asset
from integrations.home_setup import clip_graph, image_graph, node
from integrations.local import ComfyUI, Ollama
from integrations.output_evidence import graph_matches, metadata_matches, output_file
from packages.contracts.production import Shot
from packages.local_lock import exclusive_file

from .agents import CAMERAS
from .config import ROOT
from .media import asset, command, compose, input_hash
from .storage import canonical

PROVIDER = "home-local-v1"
QWEN_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
QWEN_WEIGHTS = "3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
QWEN_LICENSE = "b1e52d5a62118a2e437da900a17435b7fe914800bc1ee76e8eee04d3bd6a902e"


def new_state():
    return {"epoch": str(uuid4()), "run_token": str(uuid4()), "script_ready": False,
            "reference_ready": False, "operations": [], "models": [], "stage": "pending"}


def specs(root):
    if root is None:
        raise ValueError("Inferencia HOME desactivada en este servidor.")
    manager=root/"run/processes.json"
    if manager.exists() and json.loads(manager.read_text(encoding="utf-8")).get("ollama",{}).get("downloads_allowed"):
        raise ValueError("Ollama está en modo instalación; reinicie sin --allow-downloads antes de producir.")
    registry = json.loads((root / "licenses/verified-assets.json").read_text(encoding="utf-8"))
    found = {r["id"]: r for r in registry}
    if len(found)!=len(registry):
        raise ValueError("Registro HOME ambiguo: identificadores duplicados.")
    catalog = json.loads((ROOT / "config/home-assets.json").read_text(encoding="utf-8"))["assets"]
    expected = {r["id"]: (r["sha256"], r["license_id"], r["version"], r["license_sha256"],root/r["path"]) for r in catalog}
    expected["qwen3-4b"] = (QWEN_WEIGHTS, "Apache-2.0", QWEN_DIGEST,QWEN_LICENSE,root/"models/ollama/blobs"/("sha256-"+QWEN_WEIGHTS))
    if (root/"ComfyUI/extra_model_paths.yaml").exists():
        raise ValueError("Hay rutas ComfyUI adicionales sin auditar; no se activan pesos con esa configuración.")
    for key, (digest, license_id, version, license_hash,weight_path) in expected.items():
        row = found.get(key, {})
        if (row.get("weights_sha256"), row.get("license_id"), row.get("version")) != (digest, license_id, version):
            raise ValueError("Falta el peso/licencia fijado: " + key)
        if row.get("commercial_verified") is not True or not row.get("reviewer"):
            raise ValueError("Licencia sin revisión: " + key)
        if row.get("license_sha256")!=license_hash:
            raise ValueError("Texto de licencia distinto del auditado: "+key)
        if Path(row["weights_path"]).resolve()!=weight_path.resolve():
            raise ValueError("La ruta verificada no es la ruta de carga auditada: "+key)
        for field in ("weights_path", "license_path"):
            target = Path(row[field]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError("Archivo HOME ausente o fuera de su almacén: " + key)
    return found


@lru_cache(maxsize=32)
def verify_cached(serialized, signature):
    row = json.loads(serialized)
    verified_asset(row)
    return {k: row[k] for k in ("id", "source_url", "version", "weights_sha256", "license_id",
                                "license_sha256", "restrictions", "reviewer", "commercial_verified")}


def verify(row):
    signature = tuple((Path(row[k]).stat().st_mtime_ns, Path(row[k]).stat().st_size)
                      for k in ("weights_path", "license_path"))
    return verify_cached(json.dumps(row, sort_keys=True), signature)


def licensed_models(studio, rows, ids):
    models=[]
    for key in ids:
        model=dict(verify(rows[key]))
        text=Path(rows[key]["license_path"]).read_bytes()
        if hashlib.sha256(text).hexdigest()!=model["license_sha256"]:
            raise ValueError("El texto de licencia cambió durante la verificación.")
        model["license_asset"]={"sha256":studio.blobs.save(text),"mime":"text/plain","bytes":len(text)}
        models.append(model)
    return models


def validate_runtime(system,root):
    expected=["--listen","127.0.0.1","--port","8188","--disable-auto-launch",
              "--disable-all-custom-nodes","--offline","--preview-method","none",
              "--reserve-vram","1.5","--fast-disk"]
    argv=system.get("argv",[])
    if (system.get("comfyui_version")!="0.46.0" or not argv or
        Path(argv[0]).resolve()!=(root/"ComfyUI/main.py").resolve() or argv[1:]!=expected):
        raise ValueError("ComfyUI debe usar la versión, rutas y argumentos locales auditados del lanzador.")


def descriptor(config):
    try:
        specs(config.home_root)
        return {"name": PROVIDER, "active": True, "license": "pesos fijados; hashes comprobados al ejecutar",
                "label": "HOME · Ollama + SDXL + Wan · 480 × 832"}
    except (OSError, ValueError, KeyError) as exc:
        return {"name": PROVIDER, "active": False, "reason": str(exc)}


def persist(studio, doc, message, states=("rendering",)):
    from .production import load_doc, save
    with studio.db.transaction(write=True) as q:
        current = load_doc(q, doc["brand_id"], doc["id"])
        if current["state"] not in states or current["home"]["run_token"] != doc["home"]["run_token"]:
            return False
        doc["revision"] = current["revision"]
        save(q, doc, message)
    return True


def cancelled(studio, doc):
    from .production import load_doc
    with studio.db.transaction() as q:
        current = load_doc(q, doc["brand_id"], doc["id"])
    return current["state"] != "rendering" or current["home"]["run_token"] != doc["home"]["run_token"]


def queue_ids(client):
    queue = client.request("/queue")
    return {str(row[1]) for key in ("queue_running", "queue_pending") for row in queue[key]}


def idle(client):
    return not queue_ids(client) and not Ollama("home16").request("/api/ps").get("models")


def stage(doc):
    home = doc["home"]
    if not home["script_ready"]:
        return "script", None, "script"
    if not home["reference_ready"]:
        return "reference", None, "reference"
    if None in doc["selected"]:
        i = doc["selected"].index(None)
        return "clip", i, f"clip-{i}-{doc['attempts'][i]}-{input_hash(doc, i)}"
    return "compose", None, "compose"


def sample(operation):
    try:
        operation["peak_sampled_vram_mib"] = max(operation.get("peak_sampled_vram_mib", 0), gpu()["used_mib"])
        operation["peak_sampled_system_ram_mib"] = max(operation.get("peak_sampled_system_ram_mib", 0), used_ram() or 0)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        operation["sampling_incomplete"] = True


def fail(studio, doc, error, uncertain=False):
    if not doc["home"]["operations"] or doc["home"]["operations"][-1]["state"]=="completed":
        kind,_,key=stage(doc)
        doc["home"]["operations"].append({"id": str(uuid4()), "kind": "preflight", "for_stage":kind,
                                          "key": "preflight-"+key, "state": "failed"})
    op = doc["home"]["operations"][-1]
    op.update(state="uncertain" if uncertain else "failed", error=str(error)[:500])
    op["error_kind"] = ("uncertain" if uncertain else "out_of_memory" if "memoria" in str(error).lower()
                        else "timeout" if isinstance(error, TimeoutError) else "provider_error")
    if op["kind"] in ("reference","clip"):
        op["cancel_requested"] = not uncertain and bool(op.get("submitted_at"))
    doc.update(state="failed", error=str(error)[:500])
    persist(studio, doc, "HOME · fallo visible: " + doc["error"], states=("rendering", "failed"))
    logging.getLogger(__name__).warning(json.dumps({"event":"home_operation_failed","production_id":doc["id"],
        "request_id":op["id"],"stage":op.get("for_stage",op["kind"]),"error_kind":op["error_kind"]}))


def cancel_operation(studio, doc, client):
    op = doc["home"]["operations"][-1]
    client.cancel_atomic(op["id"])
    if op["id"] in queue_ids(client):
        return False
    op["cancel_requested"] = False
    if op["state"] not in ("failed", "uncertain"):
        op["state"] = "cancelled"
    if idle(client):
        client.request("/free", {"unload_models": True, "free_memory": True}, allow_empty=True)
    return persist(studio, doc, "HOME · petición detenida por ID", states=("cancelled", "failed", "rendering"))


def plan_from_script(doc, script):
    shots = []
    for index, caption in enumerate(script.scenes):
        seed = int.from_bytes(hashlib.sha256(canonical([doc["home"]["epoch"], index])).digest()[:4], "big")
        shots.append(Shot(order=index + 1, duration=3, caption=caption, camera=CAMERAS[index],
                          prompt=f"{doc['character']['description']}. Scene: {caption}. {CAMERAS[index]}. {doc['preset']['name']}. {doc['plan']['idea']}"[:1000], seed=seed).model_dump())
    doc["plan"].update(simulated=False, provider=PROVIDER, script=script.model_dump(), shots=shots,
                       decisions={}, trace=[{"role": "guionista", "provider": "Ollama", "prompt_version": "home-script/1",
                                            "model_digest": QWEN_DIGEST, "simulated": False, "steps": 1,
                                            "output_sha256": hashlib.sha256(canonical(script.model_dump())).hexdigest()}])
    doc["simulated"] = False


def prepare_operation(studio, doc, kind, index, key, rows):
    home = doc["home"]
    matching = [o for o in home["operations"] if o["key"] == key]
    if len(matching) >= 2:
        raise ValueError("Se agotaron dos intentos de proveedor para esta etapa; revise el fallo antes de crear otra versión.")
    ids = ["qwen3-4b"] if kind == "script" else (["sdxl-base-1.0"] if kind == "reference" else ["wan22-ti2v-5b", "wan22-umt5-fp8", "wan22-vae"])
    models = licensed_models(studio, rows, ids)
    home["models"] = list({m["id"]: m for m in [*home["models"], *models]}.values())
    op = {"id": str(uuid4()), "kind": kind, "index": index, "key": key, "state": "prepared",
          "created_at": time.time(), "models": models, "attempt": len(matching) + 1,
          "runtime_source_sha256": SOURCE_SHA256, "sampling_interval_seconds": 1 if kind=="script" else 3,
          "resources_scope": "whole_device_and_system"}
    if kind != "script":
        graph = image_graph() if kind == "reference" else clip_graph()
        if kind == "reference":
            graph["2"]["inputs"]["text"] = (f"Original character: {doc['character']['name']}. {doc['character']['description']}. {doc['preset']['name']}. {doc['plan']['idea']}. Single character, full body, vertical composition, no text, no logos.")[:1800]
            graph["5"]["inputs"]["seed"] = doc["plan"]["shots"][0]["seed"]
            graph["7"]["inputs"]["filename_prefix"] = "studio_" + op["id"]
        else:
            shot = doc["plan"]["shots"][index]
            if shot["duration"] != 3:
                raise ValueError("El perfil HOME medido admite planos de 3 segundos.")
            ref = doc["character"]["reference"]["sha256"]
            input_path = studio.db.config.home_root / "ComfyUI/input" / ("studio_" + ref + ".png")
            data = studio.blobs.read(ref)
            if not input_path.exists() or hashlib.sha256(input_path.read_bytes()).hexdigest() != ref:
                input_path.write_bytes(data)
            graph["12"] = node("LoadImage", image=input_path.name)
            graph["7"]["inputs"]["start_image"] = ["12", 0]
            graph["5"]["inputs"]["text"] = ("Preserve the exact character, proportions and colors from the reference. " + shot["prompt"] + ". Subtle natural movement, stable identity, no text, no new characters.")[:1800]
            graph["8"]["inputs"]["seed"] = (shot["seed"] + doc["attempts"][index]) % 2**32
            graph["11"]["inputs"]["filename_prefix"] = "studio_" + op["id"]
        op.update(graph=graph, workflow_sha256=hashlib.sha256(canonical(graph)).hexdigest())
    home["operations"].append(op)
    home["stage"] = kind
    persist(studio, doc, "HOME · etapa preparada: " + kind)


def collect(studio, doc, op, record, client, local_path=None):
    kind = op["kind"]
    if local_path is None and record.get("status",{}).get("status_str") != "success":
        details = [message[1] for message in record.get("status",{}).get("messages",[]) if message[0]=="execution_error"]
        detail = details[-1] if details else {}
        text = str(detail.get("exception_message", "Ejecución local incompleta"))[:300]
        if "outofmemory" in str(detail.get("exception_type", "")).lower() or "out of memory" in text.lower():
            raise RuntimeError("Memoria GPU insuficiente; cierre otros programas GPU antes de reintentar. " + text)
        raise RuntimeError("ComfyUI: " + text)
    reference=doc["character"]["reference"]["sha256"] if kind=="clip" else None
    if local_path is None:
        prompt=record.get("prompt",[])
        if len(prompt)<3 or prompt[1]!=op["id"] or not graph_matches(prompt[2],op["graph"],reference):
            raise ValueError("El historial no corresponde al ID y workflow persistidos.")
        data = client.collect(record, ".png" if kind == "reference" else ".mp4")
    else:
        data=local_path.read_bytes()
    work = studio.db.config.data / "home" / doc["id"] / op["id"]
    work.mkdir(parents=True, exist_ok=True)
    target = work / ("result.png" if kind == "reference" else "source.mp4")
    target.write_bytes(data)
    probe = json.loads(command(["ffprobe", "-v", "error", "-of", "json", "-show_streams", "-show_format", str(target)], work).stdout)
    metadata_matches(target,probe,op,reference)
    command(["ffmpeg","-hide_banner","-nostdin","-v","error","-xerror","-err_detect","explode","-i",str(target),
             "-f","null","-"],work,timeout=30)
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    if kind == "reference" and (stream["width"], stream["height"], stream["codec_name"]) != (576, 1024, "png"):
        raise ValueError("La referencia no coincide con la resolución prevista.")
    if kind == "clip":
        if (stream["width"], stream["height"]) != (480, 832) or not 2.9 <= float(probe["format"]["duration"]) <= 3.1:
            raise ValueError("El clip no coincide con el perfil HOME medido.")
        command(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(target), "-t", "3", "-an", "-r", "24",
                 "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-pix_fmt", "yuv420p", str(work / "clip.mp4")], work)
        data = (work / "clip.mp4").read_bytes()
    provenance = {"provider": PROVIDER, "request_id": op["id"], "workflow_sha256": op["workflow_sha256"],
                  "models": op["models"], "source": "local ComfyUI", "native": [stream["width"], stream["height"]],
                  "reference_sha256": reference}
    if local_path is not None:
        provenance["recovered_from"]="local-output-metadata"
        op["sampling_incomplete"]=True
    result = asset(studio.blobs, data, "image/png" if kind == "reference" else "video/mp4", simulated=False, provenance=provenance)
    sample(op)
    op.update(state="completed", result=result, completed_at=time.time(), elapsed_seconds=round(time.time() - op["submitted_at"], 3))
    if kind == "reference":
        doc["character"]["reference"] = result
        doc["home"]["reference_ready"] = True
    else:
        i = op["index"]
        clip = result | {"order": i + 1, "candidate": len(doc["candidates"][i]) + 1,
                         "seed": op["graph"]["8"]["inputs"]["seed"], "duration": 3, "renderer": PROVIDER,
                         "seconds_elapsed": op["elapsed_seconds"], "input_hash": input_hash(doc, i),
                         "resources": {k: v for k, v in op.items() if k.startswith("peak_sampled_") or k in ("sampling_interval_seconds","resources_scope")}}
        doc["candidates"][i].append(clip)
        doc["selected"][i] = clip["sha256"]
    saved=persist(studio, doc, "HOME · referencia guardada" if kind == "reference" else f"HOME · plano {op['index'] + 1}/5 guardado")
    if saved:
        try:
            if idle(client):
                client.request("/free", {"unload_models": True, "free_memory": True}, allow_empty=True)
        except (OSError,RuntimeError,ValueError):
            # El resultado ya es durable; la siguiente etapa verificará memoria.
            op["cleanup_warning"]="No se pudo confirmar liberación; comprobar antes de la siguiente inferencia."
            persist(studio,doc,"HOME · resultado guardado; liberación pendiente")


def recover_output(studio,doc,op,client):
    if op["kind"] not in ("reference","clip") or not op.get("submitted_at") or op["state"] not in ("running","submitting","uncertain"):
        return False
    path=output_file(studio.db.config.home_root,op)
    if path is None:
        return False
    # La evidencia de licencia se guardó antes de enviar a inferencia.
    saved={m["id"]:m for m in doc["home"]["models"]}
    for model in op["models"]:
        proof=saved.get(model["id"],{})
        if any(model[k]!=proof.get(k) for k in ("weights_sha256","license_sha256","version")):
            raise ValueError("La evidencia de modelo de la salida no coincide.")
        license_asset=proof.get("license_asset",{})
        if license_asset.get("sha256")!=model["license_sha256"]:
            raise ValueError("Falta el texto de licencia para recuperar sin historial.")
        studio.blobs.read(license_asset["sha256"])
    collect(studio,doc,op,None,client,local_path=path)
    return True


def advance(studio, doc):
    """Una transición; no mantiene transacción SQL mientras espera al proveedor."""
    client = ComfyUI("home16")
    home = doc["home"]
    current = home["operations"][-1] if home["operations"] else None
    if current and current.get("cancel_requested"):
        return cancel_operation(studio, doc, client)
    if doc["state"] != "rendering":
        return False
    kind, index, key = stage(doc)
    if kind == "compose":
        if any("license_asset" not in m for m in home["models"]):
            home["models"]=licensed_models(studio,specs(studio.db.config.home_root),[m["id"] for m in home["models"]])
        work = studio.db.config.data / "home" / doc["id"] / ("compose-" + str(uuid4()))
        work.mkdir(parents=True)
        doc["output"] = compose(doc, studio.blobs, work)
        doc.update(state="ready", error=None)
        home["stage"] = "ready"
        return persist(studio, doc, "HOME · montaje real y QC completados")
    rows = specs(studio.db.config.home_root)
    stats=client.request("/system_stats")
    system = stats["system"]
    validate_runtime(system,studio.db.config.home_root)
    if not current or current["key"] != key or current["state"] in ("failed", "cancelled"):
        if not idle(client):
            return False
        prepare_operation(studio, doc, kind, index, key, rows)
        return True
    op = current
    if op["kind"] == "script":
        if not idle(client):
            return False
        if op["state"] == "submitting":
            op["state"] = "failed"
            persist(studio, doc, "HOME · guion interrumpido; intento acotado")
            return True
        if not op.get("memory_release_requested_at"):
            client.request("/free",{"unload_models":True,"free_memory":True},allow_empty=True)
            op["memory_release_requested_at"]=time.time()
            persist(studio,doc,"HOME · descargando ComfyUI antes de Ollama")
            return True
        devices=stats.get("devices",[])
        reserved=sum(d.get("torch_vram_total",0) for d in devices)
        if reserved>512*1024**2:
            if time.time()-op["memory_release_requested_at"]>30:
                raise RuntimeError("No se liberó memoria ComfyUI en 30 s; revise procesos GPU.")
            return False
        op.update(state="submitting", submitted_at=time.time())
        if not persist(studio, doc, "HOME · Ollama generando guion"):
            return False
        prompt = f"Marca: {doc['brand_name']}. Idea: {doc['plan']['idea']}. Personaje: {doc['character']['name']}, {doc['character']['description']}. Cinco escenas, 15 segundos."
        done = Event()
        def sample_script():
            while not done.wait(1):
                sample(op)
        sampler = Thread(target=sample_script, daemon=True)
        sampler.start()
        try:
            script = Ollama("home16").script("qwen3:4b", QWEN_DIGEST, prompt, cancelled=lambda: cancelled(studio, doc))
        finally:
            done.set()
            sampler.join(timeout=10)
        if cancelled(studio, doc):
            return False
        plan_from_script(doc, script)
        sample(op)
        op.update(state="completed", completed_at=time.time(), script=script.model_dump(), elapsed_seconds=round(time.time() - op["submitted_at"], 3))
        home["script_ready"] = True
        return persist(studio, doc, "HOME · guion Ollama validado")
    if op["state"] == "prepared":
        if not idle(client):
            return False
        for model in op["models"]:
            verify(rows[model["id"]])
        op.update(state="submitting", submitted_at=time.time(), deadline=time.time() + 1800, submit_count=1)
        if not persist(studio, doc, "HOME · intención persistida antes de enviar " + op["kind"]):
            return False
        try:
            client.submit(canonical(op["graph"]), op["workflow_sha256"], prompt_id=op["id"])
        except (OSError, RuntimeError, ValueError) as exc:
            fail(studio, doc, "Envío con resultado incierto; reconciliar el ID antes de reintentar. " + str(exc), uncertain=True)
            return True
        op["state"] = "running"
        return persist(studio, doc, "HOME · ComfyUI aceptó " + op["id"])
    record = client.status(op["id"])
    if record:
        collect(studio, doc, op, record, client)
        return True
    if op["id"] in queue_ids(client):
        if time.time() > op["deadline"]:
            raise TimeoutError("HOME agotó el plazo de 1800 s; se detendrá el ID concreto.")
        if time.time() - op.get("heartbeat_at", 0) > 3:
            op["heartbeat_at"] = time.time()
            sample(op)
            persist(studio, doc, "HOME · en ejecución: " + kind + (f" {index + 1}/5" if index is not None else ""))
        return False
    if recover_output(studio,doc,op,client):
        return True
    if not op.get("missing_since"):
        op["missing_since"] = time.time()
        persist(studio, doc, "HOME · conciliando cola e historial")
        return False
    if time.time() - op["missing_since"] < 3:
        return False
    if home.pop("retry_requested", False):
        op["state"] = "failed"
        persist(studio, doc, "HOME · reintento explícito tras conciliación sin resultado")
    else:
        fail(studio, doc, "Resultado incierto: el ID no aparece en cola ni historial. Reintente explícitamente tras revisar ComfyUI.", uncertain=True)
    return True


def step(studio, doc):
    try:
        with exclusive_file(Path.home() / ".creative-studio-gpu.lock"):
            try:
                return advance(studio, doc)
            except (OSError, RuntimeError, ValueError, KeyError, StopIteration) as exc:
                if doc["state"] == "rendering":
                    fail(studio, doc, exc)
                return False
    except (BlockingIOError, PermissionError):
        return False
