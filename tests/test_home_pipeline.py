"""Fixtures SIMULADOS loopback; no acceden a modelos, GPU ni datos del operador."""
import hashlib
import http.client
import json
import struct
import subprocess
import tempfile
import threading
import unittest
import zlib
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from apps.api import home_runtime as home
from apps.api.backup import transfer
from apps.api.config import Config
from apps.api.export import export
from apps.api.media import Raster, rgb
from apps.api.server import build_server
from apps.api.service import Studio
from apps.api.worker import step
from integrations.local import ComfyUI, Ollama
from packages.contracts.production import ProductionDetail

REAL_SPECS = home.specs


class HomePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory(prefix="SIMULATED-home-media-")
        cls.base = Path(cls.media.name) / "fixture.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=480x832:rate=24", "-frames:v", "73", "-c:v", "libx264",
                        "-preset", "ultrafast", "-threads", "2", str(cls.base)], check=True, timeout=30)
        cls.png = Raster(576, 1024, rgb("225577")).png()

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="SIMULATED-home-pipeline-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.jobs = {}
        self.submitted = []
        self.hold = True
        self.uncertain = False
        self.oom = False
        self.free_fail=False
        self.foreign_busy=False
        self.calls=[]
        owner = self

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self):
                owner.calls.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"]))) if self.headers.get("Content-Length") else None
                result = {}
                if self.path=="/free" and owner.free_fail:
                    self.send_response(503);self.end_headers();return
                if self.path == "/api/tags":
                    result = {"models": [{"name": "qwen3:4b", "digest": home.QWEN_DIGEST}]}
                elif self.path == "/api/chat":
                    script = {"version": 1, "hook": "SIMULATED hook", "scenes": [f"SIMULATED scene {i}" for i in range(5)], "cta": "SIMULATED CTA"}
                    result = {"message": {"content": json.dumps(script)}}
                elif self.path == "/api/ps":
                    result = {"models": []}
                elif self.path == "/system_stats":
                    result = {"system": {"comfyui_version": "0.46.0", "argv": [str(owner.config.home_root/"ComfyUI/main.py"),"--listen","127.0.0.1","--port","8188","--disable-auto-launch","--disable-all-custom-nodes","--offline","--preview-method","none","--reserve-vram","1.5","--fast-disk"]}}
                elif self.path == "/prompt":
                    job = body["prompt_id"]
                    graph = body["prompt"]
                    is_clip = any(n["class_type"] == "SaveVideo" for n in graph.values())
                    filename = "studio_" + job + ("_00001_.mp4" if is_clip else "_00001_.png")
                    owner.jobs[job] = {"clip": is_clip, "filename": filename, "cancelled": False,"graph":graph}
                    owner.submitted.append(job)
                    if owner.uncertain:
                        owner.uncertain = False
                        self.send_response(503)
                        self.end_headers()
                        return
                    result = {"prompt_id": job}
                elif self.path.startswith("/history/"):
                    job = self.path.rsplit("/", 1)[-1]
                    entry = owner.jobs.get(job)
                    if entry and entry["clip"] and owner.oom:
                        result = {job: {"status": {"status_str": "error", "messages": [["execution_error", {
                            "exception_type": "torch.OutOfMemoryError", "exception_message": "CUDA out of memory"}]]}, "outputs": {}}}
                    elif entry and not entry["cancelled"] and not (entry["clip"] and owner.hold):
                        result = {job: {"prompt":[0,job,entry["graph"],{}],"status": {"status_str": "success"}, "outputs": {"out": {"images": [
                            {"filename": entry["filename"], "subfolder": "", "type": "output"}]}}}}
                elif self.path == "/queue" and body is None:
                    result = {"queue_running": [[0, k] for k, v in owner.jobs.items() if v["clip"] and owner.hold and not v["cancelled"]], "queue_pending": []}
                    if owner.foreign_busy:
                        result["queue_running"].append([0,"11111111-1111-4111-8111-111111111111"])
                elif self.path == "/interrupt" or (self.path.startswith("/api/jobs/") and self.path.endswith("/cancel")):
                    job = body["prompt_id"] if self.path == "/interrupt" else self.path.split("/")[3]
                    entry = owner.jobs.get(job)
                    if entry:
                        entry["cancelled"] = True
                elif self.path.startswith("/view?"):
                    filename = self.path.split("filename=", 1)[1].split("&", 1)[0]
                    entry=next(v for v in owner.jobs.values() if v["filename"]==filename)
                    if filename.endswith(".png"):
                        text=b"prompt\0"+json.dumps(entry["graph"]).encode()
                        chunk=struct.pack(">I",len(text))+b"tEXt"+text+struct.pack(">I",zlib.crc32(b"tEXt"+text)&0xffffffff)
                        result = owner.png[:-12]+chunk+owner.png[-12:]
                    else:
                        target = owner.root / filename
                        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(owner.base),
                                        "-c", "copy", "-metadata", "comment=SIMULATED-" + filename,
                                        "-metadata","prompt="+json.dumps(entry["graph"]),"-movflags","use_metadata_tags",str(target)], check=True, timeout=15)
                        result = target.read_bytes()
                data = result if isinstance(result, bytes) else json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_POST = do_GET = reply

        fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        thread = threading.Thread(target=fixture.serve_forever, args=(0.02,))
        thread.start()
        self.addCleanup(fixture.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(fixture.shutdown)
        root = self.root / "home"
        (root / "ComfyUI/input").mkdir(parents=True)
        rows = {}
        license_path = root / "license.txt"
        license_path.write_text("SIMULATED test license fixture")
        for key in ("qwen3-4b", "sdxl-base-1.0", "wan22-ti2v-5b", "wan22-umt5-fp8", "wan22-vae"):
            weight = root / key
            weight.write_bytes(("SIMULATED " + key).encode())
            rows[key] = {"id": key, "weights_path": str(weight), "license_path": str(license_path),
                         "weights_sha256": hashlib.sha256(weight.read_bytes()).hexdigest(),
                         "license_sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
                         "source_url": "https://example.invalid/SIMULATED", "version": "SIMULATED",
                         "license_id": "MIT", "restrictions": "SIMULATED private test fixture",
                         "reviewer": "SIMULATED test", "commercial_verified": True}
        self.rows = rows
        for name, value in [("specs", lambda root: rows), ("ComfyUI", lambda profile: ComfyUI(profile, fixture.server_port)),
                            ("Ollama", lambda profile: Ollama(profile, fixture.server_port)),
                            ("gpu", lambda: {"used_mib": 1}), ("used_ram", lambda: 1),
                            ("exclusive_file", lambda path: nullcontext())]:
            stub = patch.object(home, name, value)
            stub.start()
            self.addCleanup(stub.stop)
        self.config = Config(self.root / "data", 8765, "sqlite", "", root)
        self.server = build_server(self.config, port=0)
        thread = threading.Thread(target=self.server.serve_forever, args=(0.02,))
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)
        self.brand = self.api("GET", "/brands")[0]["id"]
        self.base_url = "/brands/" + self.brand
        campaign = self.api("POST", self.base_url + "/campaigns", {"name": "SIMULATED HOME", "objective": "SIMULATED story"})
        p = self.api("POST", self.base_url + "/productions", {"campaign_id": campaign["id"], "idea": "SIMULATED local story", "provider": home.PROVIDER})
        self.path = self.base_url + "/productions/" + p["id"]

    def api(self, method, path, body=None, status=200):
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        try:
            c.request(method, "/api/v1" + path, json.dumps(body) if body is not None else None,
                      {"Content-Type": "application/json", "Idempotency-Key": str(uuid4())})
            r = c.getresponse()
            raw = r.read()
            self.assertIn(r.status, (status, 201) if status == 200 else (status,), raw)
            return json.loads(raw)
        finally:
            c.close()

    def detail(self):
        d = self.api("GET", self.path)
        ProductionDetail.model_validate(d)
        return d

    def until(self, predicate, studio=None):
        for _ in range(80):
            doc = self.detail()
            if predicate(doc):
                return doc
            self.assertNotEqual(doc["state"], "failed", doc["error"])
            step(studio or self.server.studio)
        self.fail("SIMULATED fixture did not reach checkpoint")

    def test_recovery_cancel_selective_retry_and_backup(self):
        self.api("POST", self.path + "/render")
        running = self.until(lambda d: bool(d["home"]["operations"]) and d["home"]["operations"][-1]["kind"] == "clip" and d["home"]["operations"][-1]["state"] == "running")
        job = running["home"]["operations"][-1]["id"]
        step(Studio(self.config))  # Another worker instance reads the same SQL state.
        self.assertEqual(self.submitted.count(job), 1)
        self.api("POST", self.path + "/cancel")
        step(self.server.studio)
        self.assertTrue(self.jobs[job]["cancelled"])
        self.assertEqual(self.detail()["state"], "cancelled")
        self.hold = False
        self.api("POST", self.path + "/render")
        ready = self.until(lambda d: d["state"] == "ready", Studio(self.config))
        self.assertFalse(ready["simulated"])
        self.assertFalse(ready["plan"]["simulated"])
        self.assertTrue(ready["output"]["qc"]["passed"])
        hashes = ready["selected"][:]
        self.api("POST", self.path + "/regenerate", {"order": 3})
        again = self.until(lambda d: d["state"] == "ready")
        self.assertNotEqual(again["selected"][2], hashes[2])
        self.assertEqual(again["selected"][:2] + again["selected"][3:], hashes[:2] + hashes[3:])
        self.assertEqual(again["reviews"], [])
        self.api("POST", self.path + "/schedule", {"mode": "real"}, status=422)
        self.assertGreater(transfer(self.config.data, self.root / "backup"), 5)
        self.assertGreater(transfer(self.root / "backup", self.root / "restore", True), 5)
        export(self.server.studio,self.brand,again["id"],self.root/"export")
        self.assertTrue((self.root/"export/reel-HOME.mp4").is_file())
        self.assertEqual(len(list((self.root/"export/licencias").glob("*.txt"))),5)

    def test_ambiguous_submit_reconciles_without_second_send(self):
        self.uncertain = True
        self.api("POST", self.path + "/render")
        self.until(lambda d: d["state"] == "failed")
        failed = self.detail()
        op = failed["home"]["operations"][-1]
        self.assertEqual(op["state"], "uncertain")
        self.assertEqual(self.submitted.count(op["id"]), 1)
        self.api("POST", self.path + "/render")
        self.hold = False
        ready = self.until(lambda d: d["state"] == "ready", Studio(self.config))
        self.assertEqual(self.submitted.count(op["id"]), 1)
        self.assertTrue(ready["home"]["reference_ready"])

    def test_bad_weights_fail_before_provider_and_pin_is_enforced(self):
        Path(self.rows["qwen3-4b"]["weights_path"]).write_bytes(b"CORRUPTED SIMULATED FIXTURE")
        self.api("POST", self.path + "/render")
        failed = self.until(lambda d: d["state"] == "failed")
        self.assertIn("Hash incorrecto", failed["error"])
        self.assertEqual(self.submitted, [])
        with self.assertRaises((ValueError, OSError)):
            REAL_SPECS(self.config.home_root)

    def test_oom_is_visible_and_does_not_retry_automatically(self):
        self.oom=True
        self.hold=False
        self.api("POST",self.path+"/render")
        d=self.until(lambda d:d["state"]=="failed")
        self.assertIn("Memoria GPU insuficiente",d["error"])
        self.assertEqual(d["home"]["operations"][-1]["error_kind"],"out_of_memory")
        sent=len(self.submitted)
        for _ in range(3):
            step(self.server.studio)
        self.assertEqual(len(self.submitted),sent)
        self.assertEqual(self.detail()["selected"],[None]*5)

    def test_work_rejects_home_without_provider_connections(self):
        d=self.detail()
        disabled=Config(self.config.data,8765,"sqlite","")
        with patch.object(self.server.studio.db,"config",disabled), patch.object(home,"ComfyUI",side_effect=AssertionError("WORK called provider")):
            self.api("POST",self.base_url+"/productions",{"campaign_id":d["campaign_id"],"idea":"WORK guard","provider":home.PROVIDER},status=409)
            self.api("POST",self.path+"/render",status=409)

    def reference_running(self):
        self.api("POST",self.path+"/render")
        return self.until(lambda d: bool(d["home"]["operations"]) and d["home"]["operations"][-1]["kind"]=="reference" and d["home"]["operations"][-1]["state"]=="running")

    def test_result_is_committed_even_when_memory_cleanup_fails(self):
        self.reference_running()
        self.free_fail=True
        step(self.server.studio)
        d=self.detail()
        self.assertTrue(d["home"]["reference_ready"])
        self.assertEqual(d["home"]["operations"][-1]["state"],"completed")
        self.assertIn("cleanup_warning",d["home"]["operations"][-1])
        self.assertNotEqual(d["state"],"failed")

    def test_collection_does_not_free_another_job(self):
        self.reference_running()
        count=self.calls.count("/free")
        self.foreign_busy=True
        step(self.server.studio)
        self.assertTrue(self.detail()["home"]["reference_ready"])
        self.assertEqual(self.calls.count("/free"),count)

    def test_failed_next_preflight_keeps_completed_reference(self):
        self.reference_running()
        step(self.server.studio)
        before=self.detail()
        Path(self.rows["wan22-ti2v-5b"]["weights_path"]).write_bytes(b"SIMULATED CORRUPT WEIGHTS")
        step(self.server.studio)
        d=self.detail()
        self.assertEqual(d["state"],"failed")
        self.assertEqual(d["home"]["operations"][-2]["state"],"completed")
        self.assertEqual(d["character"]["reference"],before["character"]["reference"])
        self.assertEqual(d["home"]["operations"][-1]["for_stage"],"clip")
        self.assertFalse(d["home"]["operations"][-1].get("cancel_requested",False))

    def test_lost_history_uses_metadata_without_new_submission(self):
        self.api("POST",self.path+"/render")
        d=self.until(lambda d:bool(d["home"]["operations"]) and d["home"]["operations"][-1]["kind"]=="clip" and d["home"]["operations"][-1]["state"]=="running")
        op=d["home"]["operations"][-1]
        self.hold=False
        client=home.ComfyUI("home16")
        record=client.status(op["id"])
        data=client.collect(record,".mp4")
        folder=self.config.home_root/"ComfyUI/output"
        folder.mkdir()
        (folder/self.jobs[op["id"]]["filename"]).write_bytes(data)
        self.jobs.clear()
        sent=len(self.submitted)
        step(Studio(self.config))
        after=self.detail()
        self.assertIsNotNone(after["selected"][0])
        self.assertEqual(len(self.submitted),sent)
        self.assertEqual(after["candidates"][0][0]["provenance"]["recovered_from"],"local-output-metadata")

    def test_mismatched_output_metadata_is_blocked(self):
        self.api("POST",self.path+"/render")
        d=self.until(lambda d:bool(d["home"]["operations"]) and d["home"]["operations"][-1]["kind"]=="clip" and d["home"]["operations"][-1]["state"]=="running")
        op=d["home"]["operations"][-1]
        self.hold=False
        self.jobs[op["id"]]["graph"]["8"]["inputs"]["seed"]+=1
        client=home.ComfyUI("home16")
        record=client.status(op["id"])
        data=client.collect(record,".mp4")
        folder=self.config.home_root/"ComfyUI/output"
        folder.mkdir()
        (folder/self.jobs[op["id"]]["filename"]).write_bytes(data)
        self.jobs.clear()
        sent=len(self.submitted)
        step(self.server.studio)
        after=self.detail()
        self.assertEqual(after["state"],"failed")
        self.assertIsNone(after["selected"][0])
        self.assertEqual(len(self.submitted),sent)
        self.assertIn("grafo",after["error"].lower())
