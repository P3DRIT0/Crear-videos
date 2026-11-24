"""Copia y restauración de WORK a directorios nuevos sin seguir rutas de un manifest."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from .config import Config

DIGEST=re.compile("[0-9a-f]{64}")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def referenced(db):
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)) as cx:
        if cx.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or cx.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Base de datos inconsistente.")
        hashes={r[0] for r in cx.execute("SELECT sha256 FROM jobs WHERE sha256 IS NOT NULL")}
        tables={r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def collect(obj):
            if isinstance(obj,dict):
                if "sha256" in obj: hashes.add(obj["sha256"])
                for v in obj.values(): collect(v)
            if isinstance(obj,list):
                for v in obj: collect(v)
        for table in ("characters","productions"):
            if table in tables:
                for row in cx.execute(f"SELECT document FROM {table}"):
                    collect(json.loads(row[0]))
        if not all(isinstance(h,str) and DIGEST.fullmatch(h) for h in hashes):
            raise ValueError("Referencia de blob inválida.")
        return hashes


def transfer(source,dest,restore=False):
    source=source.resolve()
    dest=dest.absolute()
    if dest.exists() or dest.is_symlink() or dest.resolve().is_relative_to(source):
        raise ValueError("Se requiere un destino nuevo fuera del origen.")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        out=Path(tmp)/"data"
        (out/"blobs").mkdir(parents=True,mode=0o700)
        db=source/"studio.sqlite3"
        if db.is_symlink() or not db.is_file() or (source/"blobs").is_symlink():
            raise ValueError("Origen de copia inválido.")
        target=out/"studio.sqlite3"
        if restore:
            manifest=json.loads((source/"backup.json").read_text())
            shutil.copyfile(db,target)
            if sha(target)!=manifest["database"]:
                raise ValueError("Hash de la base incorrecto.")
        else:
            with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as original, closing(sqlite3.connect(target)) as new:
                original.backup(new)
        refs=sorted(referenced(target))
        if restore and refs!=manifest["blobs"]:
            raise ValueError("Inventario de blobs inconsistente.")
        for digest in refs:
            blob=source/"blobs"/digest
            if blob.is_symlink() or not blob.is_file():
                raise ValueError("Falta un blob regular.")
            copy=out/"blobs"/digest
            shutil.copyfile(blob,copy)
            if sha(copy)!=digest:
                raise ValueError("Hash incorrecto: "+digest)
        if not restore:
            (out/"backup.json").write_text(json.dumps({"version":1,"database":sha(target),"blobs":refs},indent=2))
        # Publicar solo la copia completa. mkdir falla si otro proceso ya reservó el destino.
        dest.mkdir(mode=0o700)
        os.replace(out,dest)
        return len(refs)


if __name__=="__main__":
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["backup","restore"])
    parser.add_argument("destination",type=Path)
    parser.add_argument("--source",type=Path)
    args=parser.parse_args()
    config=Config.load()
    if args.action=="restore" and not args.source:
        parser.error("Indique --source con el directorio de backup.")
    if config.backend!="sqlite":
        parser.error("Este procedimiento requiere SQLite.")
    print("Blobs verificados:",transfer(args.source or config.data,args.destination,args.action=="restore"))
