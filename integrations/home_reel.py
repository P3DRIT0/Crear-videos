"""Piloto HOME real, cinco planos I2V con referencia local. Sin aprobación ni publicación."""
import argparse
import json
import shutil
import time
from pathlib import Path

from apps.api.media import command, inspect_video, sound
from packages.contracts.production import Script

from .home import run, sha, verified_asset
from .home_setup import dump, node


def latest(root, stage, artifact):
    for folder in sorted((root / "benchmarks").glob(stage + "-*"), reverse=True):
        report_path = folder / "benchmark.json"
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        target = folder / artifact
        if report["status"] == "completed" and target.is_file() and sha(target) == report["artifact_sha256"]:
            return target
    raise ValueError("Primero complete un benchmark real de " + stage)


def checked(manifest, output, operation, *args):
    try:
        return operation(*args)
    except (Exception, KeyboardInterrupt) as exc:
        manifest.update(status="cancelled" if isinstance(exc, KeyboardInterrupt) else "failed", error=str(exc))
        dump(output / "manifest.json", manifest)
        raise


def produce(root):
    reference = latest(root, "image", "image.png")
    script_path = latest(root, "script", "script.json")
    script = Script.model_validate_json(script_path.read_bytes())
    base = json.loads((root / "manifests/clip.json").read_text(encoding="utf-8"))
    base_workflow = Path(base["workflow_path"])
    if sha(base_workflow) != base["workflow_sha256"]:
        raise ValueError("El workflow base ha cambiado desde su revisión.")
    base_graph = json.loads(base_workflow.read_text(encoding="utf-8"))
    for asset in [base, *base["additional_assets"]]:
        verified_asset(asset)
    output = root / "reels" / ("retrobay-" + time.strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True, exist_ok=False)
    input_path = root / "ComfyUI/input" / ("lumen-" + sha(reference) + ".png")
    if input_path.exists():
        if sha(input_path) != sha(reference):
            raise ValueError("La referencia de entrada ha cambiado.")
    else:
        shutil.copyfile(reference, input_path)
    reference_asset = {
        "weights_path": str(input_path), "weights_sha256": sha(input_path),
        "license_path": base["license_path"], "license_sha256": base["license_sha256"],
        "license_id": "LicenseRef-Local-Generated-SDXL", "commercial_verified": True,
        "reviewer": "Codex: cadena local SDXL verificada; no es aprobación visual humana",
        "source_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "version": sha(reference),
        "restrictions": "Imagen original generada localmente con SDXL 1.0. Respetar CreativeML Open RAIL++-M, derechos de terceros y revisión humana. No garantiza exclusividad ni identidad del personaje.",
        "provenance": {"benchmark_artifact": str(reference), "generator": "sdxl-base-1.0", "simulated": False},
    }
    actions = [
        "The robot notices a tiny light near its feet. It tilts its head gently. Slow camera push in.",
        "The robot slowly raises its hand towards a glowing light. Tiny dust particles float. Camera stays steady.",
        "The robot looks to the side towards an old arcade console. Its amber visor glows. Very subtle camera pan.",
        "The robot gently leans forward and reaches towards the old arcade console. The warm lighting slowly brightens.",
        "The robot stands proudly as the arcade lights softly pulse. The camera slowly pulls back. Calm hopeful ending.",
    ]
    shots = []
    manifest = {"schema_version": 1, "brand": "Retrobay", "title": "Lumen · La luz del arcade",
                "simulated": False, "status": "rendering", "human_review": "pending", "publication": "disabled",
                "native_resolution": [base_graph["7"]["inputs"]["width"], base_graph["7"]["inputs"]["height"]],
                "export_resolution": [1080, 1920],
                "upscaled": True, "script": script.model_dump(), "script_sha256": sha(script_path),
                "reference_sha256": sha(reference), "models": [base, *base["additional_assets"]],
                "shots": shots}
    dump(output / "manifest.json", manifest)
    for index, action in enumerate(actions):
        graph = json.loads(json.dumps(base_graph))
        graph["12"] = node("LoadImage", image=input_path.name)
        graph["7"]["inputs"]["start_image"] = ["12", 0]
        graph["5"]["inputs"]["text"] = (
            "Preserve the exact single robot from the reference image, its shape, proportions and colors. " + action
            + " Cinematic 3D animation, consistent robot identity, subtle natural movement, no text, no new characters.")
        graph["8"]["inputs"]["seed"] = 24112027 + index
        graph["11"]["inputs"]["filename_prefix"] = f"retrobay_lumen_{index + 1}"
        workflow = output / f"workflow-{index + 1}.json"
        dump(workflow, graph)
        spec = base | {"workflow_path": str(workflow), "workflow_sha256": sha(workflow),
                       "additional_assets": [*base["additional_assets"], reference_asset]}
        dump(output / f"spec-{index + 1}.json", spec)
        shot_dir = output / f"shot-{index + 1}"
        print(f"Plano real {index + 1}/5", flush=True)
        checked(manifest, output, run, spec, shot_dir)
        # Recortar los 73 frames de prueba a 72 para tres segundos exactos.
        checked(manifest, output, command, ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(shot_dir / "clip.mp4"),
                 "-t", "3", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", f"shot-{index + 1}.mp4"], output)
        report = json.loads((shot_dir / "benchmark.json").read_text(encoding="utf-8"))
        shots.append({"order": index + 1, "duration": 3, "seed": 24112027 + index,
                      "workflow_sha256": sha(workflow), "artifact_sha256": sha(output / f"shot-{index + 1}.mp4"),
                      "benchmark": report})
        dump(output / "manifest.json", manifest)
    (output / "clips.txt").write_text("".join(f"file 'shot-{i + 1}.mp4'\n" for i in range(5)), encoding="utf-8")
    captions = "\n".join(f"{i+1}\n00:00:{i*3:02},000 --> 00:00:{(i+1)*3:02},000\n{text}\n" for i, text in enumerate(script.scenes))
    (output / "subtitles.srt").write_text(captions, encoding="utf-8")
    sound([{"duration": 3}] * 5, output / "audio.wav", {"sample_rate": 24000, "frequencies_hz": [220, 262, 330, 392, 440]})
    checked(manifest, output, command, ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "1", "-i", "clips.txt",
             "-i", "audio.wav", "-i", "subtitles.srt", "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
             "-vf", "scale=1080:1920", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-r", "24", "-c:a", "aac", "-b:a", "128k", "-c:s", "mov_text", "-t", "15", "-movflags", "+faststart", "reel.mp4"], output)
    qc = inspect_video(output / "reel.mp4", 15)
    manifest.update(status="ready_for_human_review" if qc["passed"] else "qc_failed", qc=qc,
                    video_sha256=sha(output / "reel.mp4"), audio_sha256=sha(output / "audio.wav"),
                    audio_provenance="Original procedural tones generated locally; no music model or third-party recording.")
    dump(output / "manifest.json", manifest)
    if not qc["passed"]:
        raise ValueError("QC técnico fallido; consulte " + str(output))
    command(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-ss", "1", "-i", "reel.mp4", "-frames:v", "1", "cover.png"], output)
    print("Piloto real pendiente de revisión humana: " + str(output / "reel.mp4"), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    produce(parser.parse_args().root.resolve())
