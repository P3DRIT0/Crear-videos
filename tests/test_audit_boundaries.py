"""Fronteras de auditoría con archivos SIMULADOS; sin modelos ni Internet."""
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from apps.api import home_runtime as home
from apps.api.media import Raster, rgb
from integrations.output_evidence import graph_matches, output_file, png_prompt


class ModelPins(unittest.TestCase):
    def test_comfy_runtime_rejects_path_and_network_overrides(self):
        root=Path("SIMULATED-home").resolve()
        argv=[str(root/"ComfyUI/main.py"),"--listen","127.0.0.1","--port","8188","--disable-auto-launch",
              "--disable-all-custom-nodes","--offline","--preview-method","none","--reserve-vram","1.5","--fast-disk"]
        home.validate_runtime({"argv":argv,"comfyui_version":"0.46.0"},root)
        for bad in (argv+["--output-directory","elsewhere"],argv+["--extra-model-paths-config","elsewhere.yaml"],
                    [*argv[:2],"0.0.0.0",*argv[3:]], ["elsewhere/main.py",*argv[1:]]):
            with self.assertRaises(ValueError):
                home.validate_runtime({"argv":bad,"comfyui_version":"0.46.0"},root)

    def test_exact_paths_license_pins_duplicates_and_installation_mode(self):
        with tempfile.TemporaryDirectory(prefix="SIMULATED-model-pins-") as tmp:
            base=Path(tmp); root=base/"home"; repo=base/"repo"
            (repo/"config").mkdir(parents=True)
            (root/"licenses").mkdir(parents=True)
            weight=b"SIMULATED weights"
            license=b"SIMULATED license"
            digest=hashlib.sha256(weight).hexdigest(); license_hash=hashlib.sha256(license).hexdigest()
            license_path=root/"licenses/SIMULATED.txt";license_path.write_bytes(license)
            sdxl="ComfyUI/models/checkpoints/SIMULATED.safetensors"
            catalog=[{"id":"sdxl-base-1.0","path":sdxl,"sha256":digest,"license_id":"MIT","license_sha256":license_hash,"version":"SIMULATED"}]
            (repo/"config/home-assets.json").write_text(json.dumps({"assets":catalog}))
            rows=[]
            for key,relative,license_id in [("sdxl-base-1.0",sdxl,"MIT"),("qwen3-4b","models/ollama/blobs/sha256-"+digest,"Apache-2.0")]:
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(weight)
                rows.append({"id":key,"weights_path":str(path),"weights_sha256":digest,"version":"SIMULATED",
                             "license_id":license_id,"license_sha256":license_hash,"license_path":str(license_path),
                             "commercial_verified":True,"reviewer":"SIMULATED test"})
            registry=root/"licenses/verified-assets.json"
            def save():registry.write_text(json.dumps(rows))
            save()
            with patch.object(home,"ROOT",repo),patch.object(home,"QWEN_WEIGHTS",digest),patch.object(home,"QWEN_DIGEST","SIMULATED"),patch.object(home,"QWEN_LICENSE",license_hash):
                self.assertEqual(len(home.specs(root)),2)
                original=rows[0]["weights_path"]
                alias=root/"same-weights-elsewhere";alias.write_bytes(weight)
                rows[0]["weights_path"]=str(alias);save()
                with self.assertRaisesRegex(ValueError,"ruta"):
                    home.specs(root)
                rows[0]["weights_path"]=original
                rows[0]["license_sha256"]="0"*64;save()
                with self.assertRaisesRegex(ValueError,"licencia"):
                    home.specs(root)
                rows[0]["license_sha256"]=license_hash
                rows.append(dict(rows[0]));save()
                with self.assertRaisesRegex(ValueError,"duplicados"):
                    home.specs(root)
                rows.pop();save()
                (root/"run").mkdir()
                (root/"run/processes.json").write_text(json.dumps({"ollama":{"downloads_allowed":True}}))
                with self.assertRaisesRegex(ValueError,"instalación"):
                    home.specs(root)


class OutputEvidence(unittest.TestCase):
    def test_png_integrity_graph_reference_and_ambiguous_outputs(self):
        graph={"1":{"class_type":"CreateVideo","inputs":{"fps":1}}}
        data=Raster(16,16,rgb("224477")).png()
        payload=b"prompt\0"+json.dumps(graph).encode()
        chunk=struct.pack(">I",len(payload))+b"tEXt"+payload+struct.pack(">I",zlib.crc32(b"tEXt"+payload)&0xffffffff)
        png=data[:-12]+chunk+data[-12:]
        self.assertEqual(png_prompt(png),graph)
        with self.assertRaises(ValueError):png_prompt(png[:-1])
        with self.assertRaises(ValueError):png_prompt(data[:-12]+chunk+chunk+data[-12:])
        self.assertTrue(graph_matches({"1":{"class_type":"CreateVideo","inputs":{"fps":1.0}}},graph))
        self.assertFalse(graph_matches({"1":{"class_type":"CreateVideo","inputs":{"fps":True}}},graph))
        expected={"12":{"class_type":"LoadImage","inputs":{"image":"SIMULATED.png"}}}
        actual={"12":expected["12"]|{"is_changed":["a"*64]}}
        self.assertTrue(graph_matches(actual,expected,"a"*64))
        self.assertFalse(graph_matches(actual,expected,"b"*64))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/"ComfyUI/output";folder.mkdir(parents=True)
            operation={"id":str(uuid4()),"kind":"clip"}
            for n in (1,2):(folder/f"studio_{operation['id']}_{n:05}_.mp4").write_bytes(b"SIMULATED")
            with self.assertRaisesRegex(ValueError,"Varias salidas"):
                output_file(root,operation)


class ManagerState(unittest.TestCase):
    def test_state_is_preserved_when_new_snapshot_cannot_be_written(self):
        path=Path(__file__).resolve().parents[1]/"scripts/home.py"
        spec=importlib.util.spec_from_file_location("audit_home_manager",path)
        manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            manager.save_state(root,{"SIMULATED":1})
            with patch.object(manager.json,"dump",side_effect=OSError("SIMULATED disk full")),self.assertRaises(OSError):
                manager.save_state(root,{"SIMULATED":2})
            self.assertEqual(manager.read_state(root),{"SIMULATED":1})
