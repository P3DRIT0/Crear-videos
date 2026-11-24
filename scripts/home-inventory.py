"""Inventario local sin secretos: versiones, licencias y hashes de la instalación."""
import argparse
import hashlib
import json
import subprocess
from importlib.metadata import distributions
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def packages():
    records = []
    for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
        meta = dist.metadata
        name = meta["Name"]
        license_name = meta.get("License-Expression") or meta.get("License") or "; ".join(
            item for item in meta.get_all("Classifier", []) if item.startswith("License"))
        texts = []
        for file in dist.files or []:
            if file.name.lower().startswith(("license", "copying", "notice")):
                path = Path(dist.locate_file(file))
                if path.is_file():
                    texts.append({"path": str(path), "sha256": sha(path)})
        if name == "comfy-aimdo" and texts:
            license_name = "GPL-3.0 (texto incluido en el wheel)"
        if name.replace("_", "-") == "comfyui-frontend-package":
            license_name = "GPL-3.0 (fuente oficial v1.59.6; texto guardado en licenses)"
        record = next((Path(dist.locate_file(f)) for f in dist.files or [] if f.name == "RECORD"), None)
        source = (f"https://download.pytorch.org/whl/cu130/{name}/" if "+cu130" in dist.version
                  else f"https://pypi.org/project/{name}/{dist.version}/")
        records.append({"name": name, "version": dist.version,
                        "source_url": source,
                        "license": (license_name or "UNVERIFIED")[:240], "license_texts": texts,
                        "installed_record_sha256": sha(record) if record else None})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?")
    parser.add_argument("--packages", action="store_true")
    args = parser.parse_args()
    if args.packages:
        print(json.dumps(packages(), ensure_ascii=False))
        return
    root = args.root.resolve()
    output = root / "installation.json"
    ffmpeg = root / "ffmpeg/ffmpeg-9.1-essentials_build/bin/ffmpeg.exe"
    for flag, filename in [("-L", "ffmpeg-license-build.txt"), ("-buildconf", "ffmpeg-buildconf.txt")]:
        result = subprocess.run([str(ffmpeg), flag], capture_output=True, check=True, timeout=15)
        (root / "licenses" / filename).write_bytes(result.stdout + result.stderr)
    envs = {}
    for name in ("studio", "comfy"):
        python = root / f"venvs/{name}/Scripts/python.exe"
        result = subprocess.run([str(python), "-X", "utf8", __file__, "--packages"], capture_output=True, check=True, timeout=90)
        envs[name] = json.loads(result.stdout)
    archives = []
    for filename, url, license_id in [
        ("ollama-v0.40.18.zip", "https://github.com/ollama/ollama/releases/download/v0.40.18/ollama-windows-amd64.zip", "MIT; dependencias y runtime NVIDIA con avisos propios"),
        ("ffmpeg-9.1.zip", "https://github.com/GyanD/codexffmpeg/releases/download/9.1/ffmpeg-9.1-essentials_build.zip", "GPL-3.0; ver ffmpeg -L y -buildconf"),
    ]:
        path = root / "downloads" / filename
        if path.exists():
            archives.append({"file": str(path), "bytes": path.stat().st_size, "sha256": sha(path),
                             "source_url": url, "license": license_id})
    repo = Path(__file__).resolve().parents[1]
    report = {"recorded_date": "2026-11-24", "root": str(root), "profile": "home16",
              "python_runtime": {"version": "3.12.14", "source_url": "https://github.com/astral-sh/python-build-standalone",
                                 "executable_sha256": sha(root / "python/cpython-3.12-windows-x86_64-none/python.exe"),
                                 "license": "PSF-2.0 y avisos de componentes incluidos",
                                 "license_sha256": sha(root / "python/cpython-3.12-windows-x86_64-none/LICENSE.txt")},
              "comfyui": {"version": "0.46.0", "commit": "a277b5bf213e8a44fa34817b7770b54f86ef4cea",
                          "source_url": "https://github.com/Comfy-Org/ComfyUI/tree/a277b5bf213e8a44fa34817b7770b54f86ef4cea",
                          "license": "GPL-3.0", "license_sha256": sha(root / "ComfyUI/LICENSE")},
              "archives": archives, "python_packages": envs,
              "model_registry": str(root / "licenses/verified-assets.json"),
              "project_source_sha256": {str(p.relative_to(repo)): sha(p) for folder in ("apps", "packages", "integrations", "scripts")
                                        for p in (repo / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".js", ".mjs", ".cmd")},
              "licenses": [{"path": str(p), "sha256": sha(p)} for p in (root / "licenses").glob("*.txt")],
              "redistribution": "Instalación privada local. No se distribuyen binarios ni pesos. Conservar licencias, avisos y obligaciones de código fuente si se redistribuye software GPL."}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
