"""Empaqueta únicamente fuentes del estudio y documentación para traslado manual."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile

ROOT=Path(__file__).resolve().parents[1]
INCLUDE={"apps":{".py",".html",".css",".js"},"packages":{".py"},"integrations":{".py"},
         "infra":{".sql"},"config":{".yaml",".json"},"docs":{".md"},"prompts":{".md"},
         "scripts":{".py",".mjs",""},"tests":{".py",".mjs"}}


def package(dest):
    files=[ROOT/name for name in ("AGENTS.md","README.md",".gitignore",".env.example","requirements-work.lock",
                                 "requirements-home.lock","requirements-comfy-home.lock","estudio.cmd")]
    for folder,ext in INCLUDE.items():
        files.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and p.suffix in ext
                     and not any(part.startswith(".") or part=="__pycache__" for part in p.relative_to(ROOT).parts))
    hashes={}
    with ZipFile(dest,"x",compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            if path.resolve()!=path:
                raise ValueError("Se requiere una fuente regular: "+str(path))
            name=path.relative_to(ROOT).as_posix()
            data=path.read_bytes()
            hashes[name]=hashlib.sha256(data).hexdigest()
            archive.write(path,name)
        archive.writestr("SOURCE-HASHES.json",json.dumps(hashes,sort_keys=True,indent=2))
    with ZipFile(dest) as archive:
        assert archive.testzip() is None
        for name,digest in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    return len(hashes)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    print("Fuentes verificadas:",package(args.destination))
