"""Exportar un montaje confirmado a archivos con nombre y extensión."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID

from .config import Config
from .service import Studio
from .production import load_doc


def export(studio,brand,production,dest):
    with studio.db.transaction() as q:
        doc=load_doc(q,brand,production)
    if not doc["output"].get("qc",{}).get("passed"):
        raise ValueError("El montaje necesita QC superado.")
    if dest.exists() or dest.is_symlink():
        raise ValueError("Indique un destino nuevo.")
    names={"video":"reel-MOCK.mp4","cover":"portada-MOCK.png","copy":"copy.txt",
           "subtitles":"subtitulos.srt","manifest":"manifest.json","timeline":"timeline.json"}
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        bundle=Path(tmp)/"export"
        bundle.mkdir(mode=0o700)
        for key,name in names.items():
            data=studio.blobs.read(doc["output"]["assets"][key]["sha256"])
            (bundle/name).write_bytes(data)
        (bundle/"planos").mkdir(mode=0o700)
        for i,digest in enumerate(doc["selected"],1):
            (bundle/"planos"/f"{i:02}.mp4").write_bytes(studio.blobs.read(digest))
        (bundle/"storyboard.json").write_text(json.dumps(doc["plan"],ensure_ascii=False,indent=2))
        dest.mkdir(mode=0o700)
        os.replace(bundle,dest)
    return doc["output"]["assets"]["video"]["sha256"]


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("brand",type=UUID)
    parser.add_argument("production",type=UUID)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    os.umask(0o077)
    print(export(Studio(Config.load()),str(args.brand),str(args.production),args.destination))
