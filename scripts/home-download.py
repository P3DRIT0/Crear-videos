"""Descarga explícita de pesos revisados; no se importa desde el servidor."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, target):
    if not url.startswith("https://"):
        raise ValueError("Solo descargas HTTPS de las fuentes revisadas.")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl.exe", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https", "--silent", "--show-error",
                    "--retry", "2", "--continue-at", "-", "--output", str(target), url],
                   check=True, timeout=7200)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--asset", action="append")
    args = parser.parse_args()
    root = args.root.resolve()
    catalog = json.loads((ROOT / "config/home-assets.json").read_text(encoding="utf-8"))
    records = []
    registry = root / "licenses/verified-assets.json"
    if registry.exists():
        records = json.loads(registry.read_text(encoding="utf-8"))
    for asset in catalog["assets"]:
        if args.asset and asset["id"] not in args.asset:
            continue
        target = (root / asset["path"]).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Destino fuera del almacén HOME.")
        if shutil.disk_usage(root).free < (0 if target.exists() else asset["bytes"]) + 5*1024**3:
            raise RuntimeError("Espacio insuficiente con reserva de 5 GiB.")
        license_path = root / "licenses" / (asset["id"] + ".txt")
        if not license_path.exists():
            download(asset["license_url"], license_path)
        if license_path.stat().st_size < 100:
            raise ValueError("Texto de licencia incompleto.")
        print("Descarga/verificación: " + asset["id"], flush=True)
        if not target.exists():
            partial = target.with_suffix(target.suffix + ".partial")
            download(asset["url"], partial)
            if partial.stat().st_size != asset["bytes"] or sha(partial) != asset["sha256"]:
                raise ValueError("Tamaño o SHA-256 incorrecto: " + asset["id"])
            partial.rename(target)
        if target.stat().st_size != asset["bytes"] or sha(target) != asset["sha256"]:
            raise ValueError("Peso local modificado: " + asset["id"])
        record = asset | {"source_url": asset["url"], "weights_path": str(target),
                          "weights_sha256": asset["sha256"], "license_path": str(license_path),
                          "license_sha256": sha(license_path), "commercial_verified": True,
                          "reviewer": catalog["reviewed_by"]}
        if registry.exists():
            records = json.loads(registry.read_text(encoding="utf-8"))
        records = [r for r in records if r["id"] != asset["id"]] + [record]
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print("SHA-256 correcto: " + asset["id"], flush=True)


if __name__ == "__main__":
    main()
