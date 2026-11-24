import hashlib
import http.client
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from apps.api.config import Config, ROOT
from apps.api.server import build_server
from packages.contracts.models import Brief, Campaign, Job

BRAND = "720c761b-64d9-4d3c-9dd5-b1dc2e82edeb"
BASE = f"/api/v1/brands/{BRAND}"


class WorkAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(Path(self.temp.name), 8765, "sqlite", "")
        self.start()
        self.addCleanup(self.stop)

    def start(self):
        self.server = build_server(self.config, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, args=(0.02,))
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, method, path, data=None, headers=None, raw=None):
        headers = dict(headers or {})
        if data is not None:
            raw = json.dumps(data)
            headers.setdefault("Content-Type", "application/json")
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def call(self, method, path, status, data=None, key=None):
        headers = {"Idempotency-Key": key} if key else {}
        code, raw = self.request(method, path, data, headers)
        self.assertEqual(code, status, raw)
        return json.loads(raw) if raw else None

    def campaign(self, name="Lanzamiento"):
        return self.call("POST", BASE + "/campaigns", 201,
                         {"name": name, "objective": "Una ficha propia"}, str(uuid4()))

    def job(self, campaign):
        return self.call("POST", BASE + "/jobs", 201, {"label": "Ficha", "campaign_id": campaign["id"]},
                         str(uuid4()))

    def test_slice_crud_hash_restart(self):
        self.assertEqual(self.call("GET", "/api/v1/brands", 200), [{"id": BRAND, "name": "Retrobay"}])
        c = self.campaign()
        Campaign.model_validate(c)
        cp = BASE + "/campaigns/" + c["id"]
        self.call("PATCH", cp, 422, {})
        self.call("PATCH", cp, 422, {"objective": None})
        c = self.call("PATCH", cp, 200, {"objective": "Objetivo revisado"})
        self.assertEqual(c["name"], "Lanzamiento")
        self.assertEqual(self.call("GET", cp, 200), c)
        j = self.job(c)
        jp = BASE + "/jobs/" + j["id"]
        self.call("PATCH", jp, 200, {"label": "Ficha final"})
        self.call("GET", jp + "/artifact", 409)
        done = self.call("POST", jp + "/run", 200)
        Job.model_validate(done)
        self.assertEqual(done["state"], "succeeded")
        self.assertEqual(done["label"], "Ficha final")
        status, raw = self.request("GET", jp + "/artifact")
        self.assertEqual(status, 200)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), done["sha256"])
        self.assertEqual(Brief.model_validate_json(raw).campaign.objective, c["objective"])
        self.call("PATCH", cp, 200, {"name":"Cambio posterior", "objective":"Otra ficha"})
        self.stop()
        self.start()
        self.assertEqual(self.call("GET", BASE + "/jobs", 200), [done])
        self.assertEqual(self.call("POST", jp + "/run", 200), done)
        self.assertEqual(self.request("GET", jp + "/artifact")[1], raw)
        self.call("PATCH", jp, 409, {"label":"Tarde"})
        self.call("DELETE", cp, 409)
        self.call("DELETE", jp, 204)
        self.call("GET", jp + "/artifact", 404)
        self.call("DELETE", cp, 204)
        self.assertEqual(self.call("GET", BASE + "/campaigns", 200), [])

    def test_concurrent_creates_replay_and_conflict(self):
        key = str(uuid4())
        payload = {"name":"Serie A", "objective":"Continuidad"}
        def create(_):
            return self.call("POST", BASE + "/campaigns", 201, payload, key)
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(create, range(8)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(self.call("GET", BASE + "/campaigns", 200), [results[0]])
        self.call("POST", BASE + "/campaigns", 409, payload | {"name":"Otra"}, key)
        self.call("POST", BASE + "/jobs", 409, {"label":"Ficha","campaign_id":results[0]["id"]}, key)

    def test_concurrent_run_and_deduplication(self):
        c = self.campaign()
        paths = [BASE + "/jobs/" + self.job(c)["id"] + "/run" for _ in range(2)]
        with ThreadPoolExecutor(4) as pool:
            jobs = list(pool.map(lambda p: self.call("POST", p, 200), paths * 2))
        self.assertEqual(len({j["sha256"] for j in jobs}), 1)
        self.assertEqual(len(list((self.config.data / "blobs").iterdir())), 1)

    def test_brand_isolation_including_artifact_and_mutations(self):
        second = str(uuid4())
        with self.server.studio.db.transaction(write=True) as query:
            query("INSERT INTO brands VALUES (?,?)", (second,"Exyo"))
        other = f"/api/v1/brands/{second}"
        c = self.campaign()
        j = self.job(c)
        self.call("POST", BASE + "/jobs/" + j["id"] + "/run", 200)
        self.assertEqual(self.call("GET", other+"/campaigns", 200), [])
        self.call("GET", other+"/campaigns/"+c["id"], 404)
        self.call("POST", other+"/jobs", 404, {"label":"Ajeno", "campaign_id":c["id"]}, str(uuid4()))
        for method, suffix in [("POST","/run"),("GET","/artifact"),("DELETE","")]:
            self.call(method, other+"/jobs/"+j["id"]+suffix, 404)
        self.call("PATCH", other+"/campaigns/"+c["id"], 404, {"name":"Ajena","objective":"Ajena"})

    def test_storage_error_retry_and_integrity(self):
        j = self.job(self.campaign())
        path = BASE + "/jobs/" + j["id"]
        with patch.object(self.server.studio.blobs, "save", side_effect=OSError):
            failed = self.call("POST", path+"/run", 200)
        self.assertEqual(failed["state"], "failed")
        self.assertTrue(failed["error"])
        self.call("GET", path+"/artifact", 409)
        done = self.call("POST", path+"/run", 200)
        self.server.studio.blobs.path(done["sha256"]).write_bytes(b"corrupt")
        self.call("GET", path+"/artifact", 503)

    def test_health_work_contract_and_safe_paths(self):
        health = self.call("GET", "/api/v1/health", 200)
        self.assertEqual(health["schema_version"], 4)
        cap = self.call("GET","/api/v1/system/capabilities",200)
        self.assertEqual((cap["gpu_jobs"],cap["publishing"],cap["remote_inference"]), (0,False,False))
        spec = self.call("GET","/api/v1/openapi.json",200)
        self.assertIn("/api/v1/brands/{brand}/jobs/{item}/artifact",spec["paths"])
        for path in ["/../../.env","/style.css/../config.py","/blobs/123","/api/v1/publish"]:
            self.call("GET",path,404)
        with self.assertRaises(ValueError):
            self.server.studio.blobs.path("../secrets")
        with patch.object(self.server.studio.blobs, "check", side_effect=OSError):
            self.call("GET", "/api/v1/health", 503)

    def test_invalid_inputs_and_local_origin(self):
        path = BASE + "/campaigns"
        for body in [{"name":"  ","objective":"x"},{"name":"X","objective":"x","brand_id":BRAND},
                     {"name":"X","objective":"x"*1001}, {"name":3,"objective":"x"}]:
            self.call("POST",path,422,body,str(uuid4()))
        self.call("POST",path,422,{"name":"X","objective":"x"})
        self.call("GET", BASE+"/jobs/not-a-uuid",422)
        self.assertEqual(self.request("POST",path,raw="{}",headers={"Content-Type":"text/plain"})[0],415)
        self.assertEqual(self.request("POST",path,raw="z"*16385)[0],413)
        self.assertEqual(self.request("POST",path,raw="bad",headers={"Content-Type":"application/json"})[0],422)
        for headers in [{"Host":"untrusted.invalid"},{"Origin":"https://untrusted.invalid"}]:
            self.assertEqual(self.request("GET",path,headers=headers)[0],403)
        self.assertEqual(self.call("GET",path,200), [])

    def test_config_fails_closed_and_migration_reversible(self):
        for name,value in [("STUDIO_PROFILE","home32"),("STUDIO_PORT","0"),("STUDIO_DB","cloud"),
                           ("STUDIO_PG_SOCKET","external-host")]:
            with patch.dict(os.environ,{name:value}), self.assertRaises(ValueError):
                Config.load()
        with closing(sqlite3.connect(":memory:")) as conn:
            up = (ROOT/"infra/migrations/001_core.up.sql").read_text()
            conn.executescript(up)
            conn.executescript((ROOT/"infra/migrations/001_core.down.sql").read_text())
            conn.executescript(up)
            self.assertEqual(conn.execute("SELECT name FROM brands").fetchone()[0], "Retrobay")
