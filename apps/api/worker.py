"""Cola WORK de CPU; el candado del sistema se libera al terminar el proceso."""
from contextlib import contextmanager, ExitStack
from packages.local_lock import exclusive_file
import json
from pathlib import Path
import tempfile
from threading import Event
import time

from .config import Config
from .media import compose, render_shot, cancellation_check
from .production import load_doc, save
from .service import Studio


@contextmanager
def worker_slot(root):
    with ExitStack() as stack:
        try:
            stack.enter_context(exclusive_file(root/"worker.lock"))
        except (BlockingIOError,PermissionError):
            yield False
            return
        yield True


def step(studio):
    with worker_slot(studio.db.config.data) as acquired:
        if not acquired:
            return False
        with studio.db.transaction(write=True) as q:
            row=q("SELECT document FROM productions WHERE state IN ('queued','rendering') "
                  "ORDER BY CASE WHEN state='rendering' THEN 0 ELSE 1 END,id LIMIT 1").fetchone()
            if not row:
                return False
            d=json.loads(row["document"])
            if studio.db.pg:
                q("SELECT id FROM brands WHERE id=? FOR UPDATE",(d["brand_id"],))
                d=load_doc(q,d["brand_id"],d["id"])
                if d["state"] not in ("queued","rendering"):
                    return True
            if d["state"]=="queued":
                d["state"]="rendering"
                save(q,d,"Worker CPU iniciado")
        revision=d["revision"]
        def cancelled():
            with studio.db.transaction() as q:
                row=q("SELECT revision,state FROM productions WHERE id=?",(d["id"],)).fetchone()
                return row["revision"]!=revision or row["state"]!="rendering"
        token=cancellation_check.set(cancelled)
        try:
            with tempfile.TemporaryDirectory(prefix="creative-work-") as tmp:
                if None in d["selected"]:
                    i=d["selected"].index(None)
                    clip=render_shot(d,i,studio.blobs,Path(tmp))
                    if not any(c["sha256"]==clip["sha256"] for c in d["candidates"][i]):
                        d["candidates"][i].append(clip)
                    d["selected"][i]=clip["sha256"]
                    message=f"Plano {i+1}/5 guardado · MOCK"
                else:
                    d["output"]=compose(d,studio.blobs,Path(tmp))
                    d["state"]="ready"
                    message="Montaje y QC completados"
        except (OSError,RuntimeError,ValueError,KeyError,StopIteration) as exc:
            d.update(state="failed",error=str(exc)[:500])
            message="Fallo del proveedor · "+d["error"]
        finally:
            cancellation_check.reset(token)
        with studio.db.transaction(write=True) as q:
            if studio.db.pg:
                q("SELECT id FROM brands WHERE id=? FOR UPDATE",(d["brand_id"],))
            current=load_doc(q,d["brand_id"],d["id"])
            if current["revision"]==revision and current["state"]=="rendering":
                save(q,d,message)
        return True


def loop(studio, stop):
    while not stop.is_set():
        try:
            if step(studio):
                continue
        except Exception as exc:
            print(json.dumps({"event":"worker_error","exception":type(exc).__name__}),flush=True)
        stop.wait(0.75)


if __name__=="__main__":
    import os
    os.umask(0o077)
    loop(Studio(Config.load()),Event())
