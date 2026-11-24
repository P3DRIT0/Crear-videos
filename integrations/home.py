"""Benchmark local para HOME con pesos ya instalados y aprobados por el operador."""
import argparse
from packages.local_lock import exclusive_file as gpu_slot
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from threading import Event,Thread
import time

from .local import ComfyUI, Ollama


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def verified_asset(spec):
    if spec.get("commercial_verified") is not True or not str(spec.get("reviewer","")).strip():
        raise ValueError("El manifest requiere verificación comercial y revisor.")
    license_id=spec.get("license_id","")
    known={"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","CC0-1.0","CC-BY-4.0"}
    custom=re.fullmatch(r"LicenseRef-[A-Za-z0-9.-]+",license_id) and str(spec.get("restrictions","")).strip()
    if license_id not in known and not custom:
        raise ValueError("Se requiere licencia identificada o LicenseRef revisada con restricciones.")
    if not str(spec.get("source_url","")).startswith("https://") or not spec.get("version"):
        raise ValueError("Falta la fuente o la versión del artefacto.")
    for field in ("weights","license"):
        if sha(Path(spec[field+"_path"]))!=spec[field+"_sha256"]:
            raise ValueError("Hash incorrecto de "+field)


def gpu():
    result=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,memory.used","--format=csv,noheader,nounits"],
                          capture_output=True,text=True,timeout=8,check=True)
    rows=[row.rsplit(", ",2) for row in result.stdout.strip().splitlines()]
    if len(rows)!=1 or "4070 SUPER" not in rows[0][0].upper():
        raise ValueError("Este benchmark requiere el equipo HOME con la RTX 4070 SUPER.")
    return {"name":rows[0][0],"total_mib":int(rows[0][1]),"used_mib":int(rows[0][2])}


def used_ram():
    info=Path("/proc/meminfo")
    if info.is_file():
        values={s.split(":")[0]:int(s.split()[1]) for s in info.read_text().splitlines()}
        return (values["MemTotal"]-values["MemAvailable"])//1024
    if platform.system()=="Windows":
        import ctypes
        class Status(ctypes.Structure):
            _fields_=[("length",ctypes.c_uint32),("load",ctypes.c_uint32)]+[
                (k,ctypes.c_ulonglong) for k in ("total","avail","page","free_page","virt","free_virt","ext")]
        s=Status();s.length=ctypes.sizeof(s)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
            return (s.total-s.avail)//1024**2
    return None


def run(spec,out):
    if out.exists(): raise ValueError("Indique un directorio nuevo para la medición.")
    if spec.get("profile") not in ("home16","home32"): raise ValueError("Seleccione el perfil HOME tras el inventario.")
    if spec.get("offline_confirmed") is not True: raise ValueError("Confirme los servidores locales sin salida de red.")
    card=gpu()
    verified_asset(spec)
    out.parent.mkdir(parents=True,exist_ok=True)
    with gpu_slot(Path.home()/".creative-studio-gpu.lock"):
        out.mkdir(mode=0o700)
        report={"gpu":card,"profile":spec["profile"],"stage":spec["stage"],"weights_sha256":spec["weights_sha256"],
                "version":spec["version"],"peak_sampled_vram_mib":card["used_mib"],"peak_sampled_ram_mib":used_ram(),
                "sampling_seconds":1,"status":"running"}
        stop=Event()
        def sample():
            while not stop.wait(1):
                try:
                    report["peak_sampled_vram_mib"]=max(report["peak_sampled_vram_mib"],gpu()["used_mib"])
                    ram=used_ram()
                    if ram is not None:report["peak_sampled_ram_mib"]=max(report["peak_sampled_ram_mib"] or 0,ram)
                except (OSError,ValueError,subprocess.SubprocessError):
                    report["sampling_incomplete"]=True
                    return
        thread=Thread(target=sample,daemon=True);thread.start()
        start=time.monotonic()
        try:
            if spec["stage"]=="script":
                result=Ollama(spec["profile"]).script(spec["model"],spec["model_digest"],spec["idea"])
                target=out/"script.json";target.write_text(result.model_dump_json(indent=2))
            elif spec["stage"] in ("image","clip"):
                client=ComfyUI(spec["profile"])
                workflow=Path(spec["workflow_path"]).read_bytes()
                graph=json.loads(workflow)
                fields={"CheckpointLoaderSimple":"ckpt_name","UNETLoader":"unet_name","CLIPLoader":"clip_name",
                        "VAELoader":"vae_name","LoadImage":"image"}
                required={n["inputs"][fields[n["class_type"]]] for n in graph.values() if n["class_type"] in fields}
                reviewed={Path(spec["weights_path"]).name}
                for additional in spec.get("additional_assets",[]):
                    verified_asset(additional)
                    reviewed.add(Path(additional["weights_path"]).name)
                if required!=reviewed:
                    raise ValueError("Los archivos cargados por el grafo deben coincidir con los revisados.")
                settings=client.request("/object_info")
                if any(n["class_type"] not in settings for n in graph.values()):
                    raise ValueError("Faltan nodos del workflow en este servidor local.")
                job=client.submit(workflow,spec["workflow_sha256"])
                report.update(provider_job=job,workflow_sha256=spec["workflow_sha256"])
                deadline=time.monotonic()+min(1800,max(10,int(spec.get("timeout_seconds",300))))
                while time.monotonic()<deadline:
                    record=client.status(job)
                    if record: break
                    time.sleep(1)
                else:
                    client.cancel_queued(job)
                    raise TimeoutError("Timeout; verificar historial y liberar GPU antes de reintentar.")
                extension=".png" if spec["stage"]=="image" else ".mp4"
                target=out/(spec["stage"]+extension)
                target.write_bytes(client.collect(record,extension))
                probe=subprocess.run(["ffprobe","-v","error","-of","json","-show_streams","-show_format",
                                      str(target)],timeout=30,check=True,capture_output=True)
                report["probe"]=json.loads(probe.stdout)
                if spec["stage"]=="clip" and not 2.9<=float(report["probe"]["format"]["duration"])<=5.1:
                    raise ValueError("El benchmark requiere un clip de 3–5 segundos.")
                client.request("/free",{"unload_models":True,"free_memory":True},allow_empty=True)
            else:
                raise ValueError("Etapa soportada: script, image o clip.")
            report.update(status="completed",artifact_sha256=sha(target),bytes=target.stat().st_size)
        except Exception as exc:
            report.update(status="failed",error=str(exc))
            raise
        finally:
            stop.set();thread.join(10)
            report["elapsed_seconds"]=round(time.monotonic()-start,3)
            (out/"benchmark.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("manifest",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    run(json.loads(args.manifest.read_text()),args.output)
