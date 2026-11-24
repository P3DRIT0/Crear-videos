"""Checkpoint RECONSTRUIDO aislado y medios REALES; no altera el piloto original."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.api.backup import transfer
from apps.api.config import Config
from apps.api.home_runtime import step
from apps.api.production import load_doc, save
from apps.api.service import Studio
from integrations.local import ComfyUI


def main():
    root=Path(os.environ.get("STUDIO_HOME_ROOT","E:/AI-Creative-Studio")).resolve()
    identity=json.loads((root/"logs/home-browser-production.json").read_text(encoding="utf-8"))
    evidence=root/"audit"/("recovery-"+time.strftime("%Y%m%d-%H%M%S"))
    count=transfer(root/"data",evidence/"backup")
    transfer(evidence/"backup",evidence/"restored",restore=True)
    studio=Studio(Config(evidence/"restored",8765,"sqlite","",root))
    with studio.db.transaction(write=True) as q:
        doc=load_doc(q,identity["brand"],identity["production"])
        assert doc["state"]=="ready" and doc["provider"]=="home-local-v1" and doc["simulated"] is False
        assert doc["title"].startswith("Retrobay · Integración HOME")
        op=doc["home"]["operations"][-1]
        assert op["kind"]=="clip" and op["state"]=="completed"
        i=op["index"]
        original=doc["selected"][i]
        assert original==op["result"]["sha256"]
        doc["candidates"][i]=[c for c in doc["candidates"][i] if c["sha256"]!=original]
        doc["selected"][i]=None
        doc.update(state="rendering",output={},error=None)
        op["state"]="running"
        for key in ("result","completed_at","elapsed_seconds"):
            op.pop(key,None)
        save(q,doc,"AUDIT: checkpoint RECONSTRUIDO solo en copia aislada")
    assert ComfyUI("home16").status(op["id"]) is None
    ffmpeg=root/"ffmpeg/ffmpeg-9.1-essentials_build/bin"
    os.environ["PATH"]=str(ffmpeg)+os.pathsep+os.environ.get("PATH","")
    with patch.object(ComfyUI,"submit",side_effect=AssertionError("No se permite reenviar inferencia en esta prueba")) as submit:
        assert step(studio,doc)
        assert submit.call_count==0
    with studio.db.transaction() as q:
        result=load_doc(q,identity["brand"],identity["production"])
    recovered=result["candidates"][i][-1]
    assert result["selected"][i]==original,(result.get("error"),result["selected"][i],original)
    assert recovered["provenance"]["recovered_from"]=="local-output-metadata"
    assert hashlib.sha256(studio.blobs.read(original)).hexdigest()==original
    report={"checkpoint_reconstructed":True,"media_simulated":False,"original_data_modified":False,
            "production":doc["id"],"prompt_id":op["id"],"stage":i+1,"provider_history_missing":True,
            "new_submissions":submit.call_count,"same_clip_sha256":original,"backup_verified_blobs":count,
            "reviews":result["reviews"],"publishing":False,"scope":"single transition on isolated restored SQL snapshot"}
    (evidence/"evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    print(evidence)


if __name__=="__main__":
    main()
