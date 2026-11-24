import hashlib
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from uuid import uuid4

from integrations.home import verified_asset,gpu_slot
from integrations.local import ComfyUI,Ollama


class LocalContracts(unittest.TestCase):
    def test_loopback_fixture(self):
        job=str(uuid4())
        calls=[]
        script={"version":1,"hook":"Prueba","scenes":["Escena"]*5,"cta":"Fin"}
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def reply(self):
                length=int(self.headers.get("Content-Length","0"))
                body=json.loads(self.rfile.read(length)) if length else None
                calls.append((self.path,body))
                result={
                    "/api/tags":{"models":[{"name":"fixture:1","digest":"a"*64}]},
                    "/api/chat":{"message":{"content":json.dumps(script)}},
                    "/prompt":{"prompt_id":job},
                    "/history/"+job:{job:{"status":{"status_str":"success"},"outputs":{"1":{"images":[
                        {"filename":"fixture.png","subfolder":"","type":"output"}]}}}},
                    "/queue":{}, "/view?filename=fixture.png&type=output":b"MOCK fixture",
                }[self.path]
                data=result if isinstance(result,bytes) else json.dumps(result).encode()
                self.send_response(200);self.send_header("Content-Length",str(len(data)));self.end_headers()
                self.wfile.write(data)
            do_POST=do_GET=reply
        with ThreadingHTTPServer(("127.0.0.1",0),Fixture) as server:
            thread=threading.Thread(target=server.serve_forever,args=(0.02,));thread.start()
            try:
                for cls in [Ollama,ComfyUI]:
                    with self.assertRaises(ValueError):cls("work",server.server_port)
                ollama=Ollama("home16",server.server_port)
                with self.assertRaises(ValueError):ollama.script("x:cloud","a"*64,"x")
                self.assertEqual(ollama.script("fixture:1","a"*64,"Idea").scenes,script["scenes"])
                client=ComfyUI("home32",server.server_port)
                graph=b'{"1":{"class_type":"EmptyImage","inputs":{}}}'
                with self.assertRaises(ValueError):client.submit(graph,"a"*64)
                self.assertEqual(client.submit(graph,hashlib.sha256(graph).hexdigest()),job)
                self.assertEqual(client.collect(client.status(job),".png"),b"MOCK fixture")
                client.cancel_queued(job)
                self.assertEqual(calls[-1],("/queue",{"delete":[job]}))
            finally:
                server.shutdown();thread.join()

    def test_home_hash_license_and_single_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"weights";path.write_bytes(b"FIXTURE")
            license=Path(tmp)/"license";license.write_text("FIXTURE")
            spec={"commercial_verified":True,"reviewer":"test","source_url":"https://example.invalid",
                  "license_id":"MIT","version":"test","weights_path":str(path),"license_path":str(license),
                  "weights_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"license_sha256":hashlib.sha256(license.read_bytes()).hexdigest()}
            verified_asset(spec)
            for override in ({"license_id":"unknown"},{"weights_sha256":"0"*64},{"commercial_verified":False}):
                with self.assertRaises(ValueError):verified_asset(spec|override)
            lock=Path(tmp)/"lock"
            with gpu_slot(lock),self.assertRaises(OSError):
                with gpu_slot(lock): pass
