"""Prueba REAL opt-in sobre el piloto técnico creado por home-browser-smoke.mjs."""
import http.client
import json
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path("E:/AI-Creative-Studio")
identity = json.loads((ROOT / "logs/home-browser-production.json").read_text(encoding="utf-8"))
path = "/api/v1/brands/" + identity["brand"] + "/productions/" + identity["production"]


def api(action=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", 8765, timeout=15)
    try:
        c.request("POST" if action else "GET", path + ("/" + action if action else ""),
                  json.dumps(body) if body is not None else None,
                  {"Content-Type": "application/json", "Idempotency-Key": str(uuid4())})
        r = c.getresponse()
        data = json.loads(r.read())
        if r.status != 200:
            raise RuntimeError(str(data))
        return data
    finally:
        c.close()


def wait(predicate, seconds=1200):
    end = time.time() + seconds
    while time.time() < end:
        d = api()
        assert d["title"].startswith("Retrobay · Integración HOME")
        if predicate(d):
            return d
        if d["state"] == "failed":
            raise RuntimeError(d["error"])
        time.sleep(1)
    raise TimeoutError("El piloto real no alcanzó el checkpoint.")


def snapshot(name, doc):
    (ROOT / "logs" / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


before = json.loads((ROOT / "logs/home-before-restart.json").read_text(encoding="utf-8"))
first_id = before["home"]["operations"][-1]["id"]
d = wait(lambda d: d["selected"][0] is not None)
recovered = next(o for o in d["home"]["operations"] if o["id"] == first_id)
assert recovered["state"] == "completed" and recovered["submit_count"] == 1
files = list((ROOT / "ComfyUI/output").glob("studio_" + first_id + "*.mp4"))
assert len(files) == 1, files
snapshot("home-recovered.json", d)
print("Recuperación real: mismo ID y una sola salida", flush=True)
proof=ROOT/"logs/home-cancelled.json"
cancel_proof=json.loads(proof.read_text(encoding="utf-8")) if proof.exists() else {}
if cancel_proof.get("id")==identity["production"]:
    saved=cancel_proof["selected"][:]
    print("Se conserva la evidencia de cancelación real de este mismo piloto.",flush=True)
else:
    d = wait(lambda d: d["home"]["operations"][-1]["kind"] == "clip" and d["home"]["operations"][-1]["state"] == "running" and d["home"]["operations"][-1]["index"] >= 1)
    saved = d["selected"][:]
    cancelled_id = d["home"]["operations"][-1]["id"]
    api("cancel")
    d = wait(lambda d: d["state"] == "cancelled" and not d["home"]["operations"][-1].get("cancel_requested"), seconds=90)
    assert d["selected"] == saved
    snapshot("home-cancelled.json", d)
    print("Cancelación real por ID confirmada: " + cancelled_id, flush=True)
    api("render")
d = wait(lambda d: d["state"] == "ready")
assert all(old is None or old == new for old, new in zip(saved, d["selected"]))
assert d["reviews"] == [] and d.get("active_review") is None
snapshot("home-ready-before-regeneration.json", d)
print("Reanudación real y QC completados", flush=True)
hashes = d["selected"][:]
api("regenerate", {"order": 3})
d = wait(lambda d: d["state"] == "ready")
assert d["selected"][2] != hashes[2]
assert d["selected"][:2] + d["selected"][3:] == hashes[:2] + hashes[3:]
assert len(d["candidates"][2]) == 2 and d["reviews"] == [] and d.get("active_review") is None
snapshot("home-recovery-final.json", d)
print("Regeneración real: solo cambia el tercer plano. Sin aprobación ni publicación.", flush=True)
