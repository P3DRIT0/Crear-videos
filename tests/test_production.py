import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from apps.api.agents import preset_data, storyboard
from apps.api.backup import transfer
from apps.api.config import Config,ROOT
from apps.api.server import build_server
from apps.api.worker import step,worker_slot
from packages.contracts.production import ProductionDetail


class ProductionHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config=Config(Path(self.tmp.name)/"live",8765,"sqlite","")
        self.server=build_server(self.config,port=0)
        t=threading.Thread(target=self.server.serve_forever,args=(0.02,))
        t.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(t.join)
        self.addCleanup(self.server.shutdown)
        self.brand=self.api("GET","/brands")[0]["id"]
        self.base="/brands/"+self.brand
        self.campaign=self.api("POST",self.base+"/campaigns",{"name":"Piloto","objective":"Recorrer una ciudad nocturna."})
        self.body={"campaign_id":self.campaign["id"],"idea":self.campaign["objective"]}
        self.project=self.api("POST",self.base+"/productions",self.body)
        self.path=self.base+"/productions/"+self.project["id"]

    def api(self,method,path,body=None,status=None,key=None,binary=False):
        client=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=10)
        try:
            client.request(method,"/api/v1"+path,body=json.dumps(body) if body is not None else None,
                           headers={"Content-Type":"application/json","Idempotency-Key":key or str(uuid4())})
            res=client.getresponse()
            data=res.read()
            if status is not None: self.assertEqual(res.status,status,data[:200])
            else: self.assertIn(res.status,(200,201),data[:200])
            return data if binary else json.loads(data)
        finally: client.close()

    def detail(self):
        d=self.api("GET",self.path)
        ProductionDetail.model_validate(d)
        return d

    def finish(self):
        for _ in range(7):
            if not step(self.server.studio): break
        d=self.detail()
        self.assertEqual(d["state"],"ready",d["error"])
        return d

    def test_contract_roles_offline_limits_and_brand_isolation(self):
        d=self.detail()
        other=self.api("POST","/brands",{"name":"Exyo"})
        self.api("GET",self.path.replace(self.brand,other["id"]),status=404)
        self.api("POST","/brands/"+other["id"]+"/productions",self.body,status=404)
        self.api("POST",self.base+"/productions",self.body|{"preset":"unknown"},status=422)
        self.api("POST",self.base+"/productions",self.body|{"idea":""},status=422)
        self.api("DELETE",self.base+"/campaigns/"+self.campaign["id"],status=409)
        with patch.object(socket.socket,"connect",side_effect=AssertionError("Egreso inesperado")):
            args=(self.body["idea"],self.campaign["name"],"Retrobay",preset_data("motion"),d["character"])
            self.assertEqual(storyboard(*args),d["plan"])
            with self.assertRaises(TimeoutError): storyboard(*args,timeout=0)
        char=self.api("POST",self.base+"/characters",{"name":"Rayo","description":"Visor y botas.","color":"#114477"})
        again=self.api("POST",self.base+"/characters",{"name":"Rayo","description":"Otro color.","color":"#884411"})
        self.assertEqual((char["version"],again["version"]),(1,2))
        self.api("POST","/brands/"+other["id"]+"/productions",self.body|{"character_id":char["id"]},status=404)
        record={"name":"Candidato","version":"1","source_url":"https://example.invalid/model","sha256":"a"*64,
                "license_id":"desconocida","restrictions":"Pendiente de auditoría","checked_by":"Fixture"}
        self.assertFalse(self.api("POST",self.base+"/models",record)["enabled"])
        self.assertEqual(self.api("GET",self.base+"/registry")["models"][0]["status"],"pending_local_validation")
        self.api("POST",self.path+"/schedule",{"mode":"real"},status=422)
        self.api("POST",self.path+"/publish",status=404)
        self.api("GET",self.path+"/assets/"+"a"*64,status=404)
        self.api("GET",self.path+"/assets/../../.env",status=404)

    def test_regeneration_budget_edit_and_timeline(self):
        self.api("POST",self.path+"/render")
        def fixture(doc,index,store,work):
            shot=doc["plan"]["shots"][index]
            from apps.api.storage import canonical
            return {"sha256":store.save(canonical([shot,doc["attempts"][index]])),"mime":"video/mp4",
                    "license":"original-procedural-v1","simulated":True,"candidate":doc["attempts"][index]+1,
                    "input_hash":hashlib.sha256(canonical(shot)).hexdigest()}
        with patch("apps.api.worker.render_shot",side_effect=fixture), patch("apps.api.worker.compose",return_value={"assets":{},"qc":{"passed":True}}):
            self.finish()
            for _ in range(2):
                self.api("POST",self.path+"/regenerate",{"order":3})
                self.finish()
            self.api("POST",self.path+"/regenerate",{"order":3},status=409)
        d=self.detail()
        self.assertEqual([len(g) for g in d["candidates"]],[1,1,3,1,1])
        self.api("POST",self.path+"/sequence",{"orders":[2,1,3,4,5],"revision":d["revision"]})
        self.assertEqual(self.detail()["selected"],d["selected"])
        self.api("POST",self.path+"/sequence",{"orders":[2,2,3,4,5],"revision":d["revision"]},status=422)
        self.api("POST",self.path+"/rewrite",{"idea":"Un nuevo guion","revision":self.detail()["revision"]})
        self.assertEqual(self.detail()["selected"],[None]*5)
        self.assertFalse(self.detail()["candidates"][2][0]["selectable"])

    def test_brand_policy_limits_and_reconciliation(self):
        rules={"daily_limit":1,"start_hour":10,"end_hour":17,"min_score":3,"paused":False}
        self.api("POST",self.base+"/policy",rules)
        self.api("POST",self.base+"/policy",rules|{"start_hour":23},status=422)
        second=self.api("POST",self.base+"/productions",self.body)
        paths=[self.path,self.base+"/productions/"+second["id"]]
        digest="b"*64
        # Fixtures de contrato sin codificar MP4 para comprobar la política transaccional.
        with self.server.studio.db.transaction(write=True) as q:
            for pid in [self.project["id"],second["id"]]:
                d=json.loads(q("SELECT document FROM productions WHERE id=?",(pid,)).fetchone()["document"])
                d.update(state="ready",output={"assets":{"video":{"sha256":digest,"license":"original-procedural-v1"}},"qc":{"passed":True}})
                q("UPDATE productions SET state='ready',document=? WHERE id=?",(json.dumps(d),pid))
        for path in paths:
            self.api("POST",path+"/review",{"artifact_hash":digest,"reviewer":"TEST","verdict":"approved",
                     "continuity":3,"movement":3,"narrative":3,"notes":"Fixture local"})
        when={"artifact_hash":digest,"copy":"Fixture","scheduled_at":"2025-12-01T11:00:00Z"}
        self.api("POST",paths[0]+"/schedule",when|{"scheduled_at":"2025-12-01T20:00:00Z"},status=409)
        record=self.api("POST",paths[0]+"/schedule",when)
        self.api("POST",paths[1]+"/schedule",when,status=409)
        self.api("POST",self.base+"/policy",rules|{"paused":True})
        pub=self.base+"/publications/"+record["id"]
        self.api("POST",pub+"/simulate",status=409)
        self.api("POST",pub+"/stop")
        self.api("POST",self.base+"/policy",rules)
        self.api("POST",paths[1]+"/schedule",when)
        self.api("POST",pub+"/simulate",status=409)

    def test_worker_failure_cancel_and_sse_resume(self):
        self.api("POST",self.path+"/render")
        with worker_slot(self.config.data) as held:
            self.assertTrue(held)
            self.assertFalse(step(self.server.studio))
        with patch("apps.api.worker.render_shot",side_effect=RuntimeError("Timeout de prueba")):
            step(self.server.studio)
        self.assertIn("Timeout",self.detail()["error"])
        self.api("POST",self.path+"/render")
        started=threading.Event()
        resume=threading.Event()
        def slow(*args):
            started.set();resume.wait(3)
            raise RuntimeError("Resultado obsoleto")
        with patch("apps.api.worker.render_shot",side_effect=slow):
            thread=threading.Thread(target=step,args=(self.server.studio,))
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                self.api("POST",self.path+"/cancel")
            finally:
                resume.set();thread.join()
        d=self.detail()
        self.assertEqual(d["state"],"cancelled")
        self.assertFalse(any(d["candidates"]))
        client=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            client.request("GET","/api/v1"+self.path+"/events",headers={"Last-Event-ID":str(d["revision"]-1)})
            res=client.getresponse()
            self.assertEqual(res.getheader("Content-Type"),"text/event-stream")
            self.assertEqual(res.readline(),b"retry: 1000\n")
            res.readline()
            self.assertEqual(res.readline(),f"id: {d['revision']}\n".encode())
            self.assertIn("Cancelación",res.readline().decode())
        finally: client.close()

    def test_real_reel_restart_regeneration_review_dry_run_and_restore(self):
        self.api("POST",self.path+"/render")
        worker=subprocess.Popen([sys.executable,"-m","apps.api.worker"],cwd=ROOT,
            env={**os.environ,"STUDIO_DATA":str(self.config.data),"STUDIO_DB":"sqlite","STUDIO_PROFILE":"work"},
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                d=self.detail()
                if d["state"]=="rendering" and any(d["selected"]): break
                time.sleep(0.03)
            self.assertTrue(any(d["selected"]))
            self.assertEqual(d["state"],"rendering")
        finally:
            worker.kill();worker.communicate(timeout=5)
        recovered=self.finish()
        for old,new in zip(d["selected"],recovered["selected"]):
            if old: self.assertEqual(old,new)
        self.assertEqual([len(c) for c in recovered["candidates"]],[1]*5)
        assets=recovered["output"]["assets"]
        for name,a in assets.items():
            data=self.api("GET",self.path+"/assets/"+a["sha256"],binary=True)
            self.assertEqual(hashlib.sha256(data).hexdigest(),a["sha256"],name)
        digest=assets["video"]["sha256"]
        when={"artifact_hash":digest,"copy":"MOCK · fixture","scheduled_at":"2026-01-01T10:00:00Z"}
        self.api("POST",self.path+"/schedule",when,status=409)
        review={"artifact_hash":digest,"reviewer":"TEST AUTOMÁTICO","verdict":"approved","continuity":4,
                "movement":4,"narrative":4,"notes":"Fixture de contrato, sin juicio humano."}
        self.api("POST",self.path+"/review",review|{"artifact_hash":"0"*64},status=409)
        self.api("POST",self.path+"/review",review|{"movement":1},status=409)
        self.api("POST",self.path+"/review",review)
        self.api("POST",self.path+"/schedule",when|{"mode":"real"},status=422)
        key=str(uuid4())
        pub=self.api("POST",self.path+"/schedule",when,key=key)
        self.assertEqual(self.api("POST",self.path+"/schedule",when,key=key),pub)
        self.assertEqual(self.api("POST",self.path+"/schedule",when)["id"],pub["id"])
        dest=self.base+"/publications/"+pub["id"]+"/simulate"
        self.assertEqual(self.api("POST",dest)["status"],"dry_run")
        self.assertEqual(self.api("POST",dest)["status"],"dry_run")
        self.assertEqual(self.api("GET",self.base+"/metrics")["counts"],{"dry_run":1})
        self.api("POST",self.path+"/regenerate",{"order":3})
        second=self.finish()
        self.assertNotEqual(second["selected"][2],recovered["selected"][2])
        for i in (0,1,3,4): self.assertEqual(second["selected"][i],recovered["selected"][i])
        self.api("POST",self.path+"/schedule",when,status=409)
        self.api("POST",self.path+"/select",{"order":3,"sha256":recovered["selected"][2]})
        self.api("POST",self.path+"/render")
        previous=self.finish()
        self.assertEqual(previous["output"]["assets"]["video"]["sha256"],digest)
        self.api("POST",self.path+"/schedule",when,status=409)
        edit={"order":2,"caption":"Cambio","duration":3,"prompt":"Luz lateral","revision":previous["revision"]}
        self.api("POST",self.path+"/edit",edit)
        self.api("POST",self.path+"/edit",edit,status=409)
        edited=self.detail()
        self.assertIsNone(edited["selected"][1])
        self.assertEqual(len(edited["plan_history"]),1)
        self.api("POST",self.path+"/select",{"order":2,"sha256":recovered["selected"][1]},status=409)
        source=self.config.data; backup=source.parent/"backup"; dest=source.parent/"restore"
        self.assertGreater(transfer(source,backup),5)
        transfer(backup,dest,restore=True)
        with self.assertRaises(ValueError):transfer(backup,dest,restore=True)
        self.assertEqual((dest/"blobs"/digest).read_bytes(),(source/"blobs"/digest).read_bytes())
        (backup/"blobs"/digest).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):transfer(backup,source.parent/"broken",restore=True)
        self.assertFalse((source.parent/"broken").exists())
