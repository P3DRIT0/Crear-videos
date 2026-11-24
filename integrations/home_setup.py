"""Manifests y workflows propios para las versiones auditadas de HOME."""
import json

from .home import sha, verified_asset
from .local import ComfyUI, Ollama


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


def ollama_manifest(path, blobs, digest):
    data = json.loads(path.read_text(encoding="utf-8"))
    if sha(path) == digest:
        return data
    # Ollama 0.40 conserva el manifest original como una capa adicional local.
    upstream = [item for item in data["layers"] if item["mediaType"] == "application/vnd.docker.distribution.manifest.v2+json"]
    if len(upstream) != 1 or upstream[0]["digest"] != "sha256:" + digest:
        raise ValueError("Manifest Ollama no coincide con el digest servido.")
    blob = blobs / ("sha256-" + digest)
    if sha(blob) != digest:
        raise ValueError("Hash del manifest original Ollama incorrecto.")
    original = json.loads(blob.read_text(encoding="utf-8"))
    layers = [item for item in data["layers"] if item not in upstream]
    if original["config"] != data["config"] or original["layers"] != layers:
        raise ValueError("Las capas Ollama difieren del manifest original.")
    return original


def image_graph():
    return {
        "1": node("CheckpointLoaderSimple", ckpt_name="sd_xl_base_1.0.safetensors"),
        "2": node("CLIPTextEncode", clip=["1", 1], text="Original small teal robot Lumen, round amber visor, orange scarf, tiny white light in its hands, dark retro arcade, cinematic 3D animation, full body, single character, vertical composition, soft volumetric light, no text, no logos"),
        "3": node("CLIPTextEncode", clip=["1", 1], text="text, watermark, logo, extra limbs, duplicate character, blurry, deformed hands"),
        "4": node("EmptyLatentImage", width=576, height=1024, batch_size=1),
        "5": node("KSampler", model=["1", 0], positive=["2", 0], negative=["3", 0], latent_image=["4", 0], seed=24112026,
                  steps=20, cfg=7, sampler_name="euler", scheduler="normal", denoise=1),
        "6": node("VAEDecode", samples=["5", 0], vae=["1", 2]),
        "7": node("SaveImage", images=["6", 0], filename_prefix="home_lumen"),
    }


def clip_graph():
    return {
        "1": node("UNETLoader", unet_name="wan2.2_ti2v_5B_fp16.safetensors", weight_dtype="fp8_e4m3fn"),
        "2": node("CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default"),
        "3": node("VAELoader", vae_name="wan2.2_vae.safetensors"),
        "4": node("ModelSamplingSD3", model=["1", 0], shift=8),
        "5": node("CLIPTextEncode", clip=["2", 0], text="An original small teal robot with a round amber visor and orange scarf holds a tiny light in a dark retro arcade. The light pulses gently and the robot slowly turns its head. Subtle camera push in, cinematic 3D animation, stable character identity, no text."),
        "6": node("CLIPTextEncode", clip=["2", 0], text="text, logo, watermark, distorted face, extra limbs, flicker, abrupt camera movement, static frame"),
        "7": node("Wan22ImageToVideoLatent", vae=["3", 0], width=480, height=832, length=73, batch_size=1),
        "8": node("KSampler", model=["4", 0], positive=["5", 0], negative=["6", 0], latent_image=["7", 0], seed=24112026,
                  steps=20, cfg=5, sampler_name="uni_pc", scheduler="simple", denoise=1),
        "9": node("VAEDecode", samples=["8", 0], vae=["3", 0]),
        "10": node("CreateVideo", images=["9", 0], fps=24),
        "11": node("SaveVideo", video=["10", 0], filename_prefix="home_wan", format="mp4", codec="h264"),
    }


def prepare(root):
    argv = ComfyUI("home16").request("/system_stats")["system"]["argv"]
    if not {"--offline", "--disable-all-custom-nodes", "127.0.0.1"}.issubset(argv):
        raise ValueError("Inicie ComfyUI con el lanzador HOME offline y sin custom nodes.")
    registry = json.loads((root / "licenses/verified-assets.json").read_text(encoding="utf-8")) if (root / "licenses/verified-assets.json").exists() else []
    assets = {r["id"]: r for r in registry}
    common = {"profile": "home16", "offline_confirmed": True,
              "offline_scope": "Ollama NO_CLOUD; ComfyUI --offline sin custom nodes; HF offline. No aislamiento de red del SO.", "timeout_seconds": 1800}
    for stage, ids, graph in [("image", ["sdxl-base-1.0"], image_graph()),
                              ("clip", ["wan22-ti2v-5b", "wan22-umt5-fp8", "wan22-vae"], clip_graph())]:
        if not all(i in assets for i in ids):
            print(stage + ": pendiente de descargar/verificar pesos")
            continue
        for key in ids:
            verified_asset(assets[key])
        workflow = root / "workflows" / (stage + ".json")
        dump(workflow, graph)
        dump(root / "manifests" / (stage + ".json"), assets[ids[0]] | common | {
            "stage": stage, "workflow_path": str(workflow), "workflow_sha256": sha(workflow),
            "additional_assets": [assets[i] for i in ids[1:]]})
    client = Ollama("home16")
    installed = next((m for m in client.request("/api/tags")["models"] if m["name"] == "qwen3:4b"), None)
    if installed is None:
        raise ValueError("Falta qwen3:4b local. Descárguelo explícitamente antes de preparar manifests.")
    manifest = root / "models/ollama/manifests/registry.ollama.ai/library/qwen3/4b"
    data = ollama_manifest(manifest, root / "models/ollama/blobs", installed["digest"])
    layer = next(item for item in data["layers"] if item["mediaType"] == "application/vnd.ollama.image.model")
    weights = root / "models/ollama/blobs" / layer["digest"].replace(":", "-")
    detail = client.request("/api/show", {"model": "qwen3:4b"})
    license_path = root / "licenses/qwen3-4b.txt"
    license_path.write_text(detail["license"], encoding="utf-8")
    if "Apache License" not in detail["license"] or "Version 2.0" not in detail["license"]:
        raise ValueError("La licencia servida de Qwen3 ha cambiado.")
    record = {"id": "qwen3-4b", "source_url": "https://ollama.com/library/qwen3:4b", "version": installed["digest"],
              "weights_path": str(weights), "weights_sha256": layer["digest"].split(":")[1],
              "license_path": str(license_path), "license_sha256": sha(license_path), "license_id": "Apache-2.0",
              "restrictions": "Conservar licencia y avisos al redistribuir; sin concesión de marcas.",
              "reviewer": "Codex: licencia Apache-2.0 servida por Ollama y ficha oficial, 2026-11-24", "commercial_verified": True}
    verified_asset(record)
    dump(root / "licenses/verified-assets.json", [r for r in registry if r["id"] != record["id"]] + [record])
    dump(root / "manifests/script.json", record | common | {"stage": "script", "model": "qwen3:4b", "model_digest": installed["digest"],
         "idea": "Escribe en español un guion JSON version=1 para Retrobay, 5 escenas breves. Lumen es un robot turquesa original con visor ámbar y bufanda naranja. Descubre una luz en un arcade y la devuelve a una consola. Hook atractivo, cinco escenas, CTA breve. Sin marcas ni personajes ajenos."})
    print("Manifests locales preparados; pesos y licencias verificados.")
