import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from integrations.home_setup import ollama_manifest


class OllamaManifest(unittest.TestCase):
    def test_original_and_wrapped_manifest_reject_modified_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {"config": {"digest": "config"}, "layers": [{"mediaType": "weights", "digest": "weights"}]}
            raw = json.dumps(original).encode()
            digest = hashlib.sha256(raw).hexdigest()
            manifest = root / "manifest"
            manifest.write_bytes(raw)
            self.assertEqual(ollama_manifest(manifest, root, digest), original)
            (root / ("sha256-" + digest)).write_bytes(raw)
            wrapped = original | {"layers": original["layers"] + [{
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json", "digest": "sha256:" + digest}]}
            manifest.write_text(json.dumps(wrapped), encoding="utf-8")
            self.assertEqual(ollama_manifest(manifest, root, digest), original)
            wrapped["config"] = {"digest": "modified"}
            manifest.write_text(json.dumps(wrapped), encoding="utf-8")
            with self.assertRaises(ValueError):
                ollama_manifest(manifest, root, digest)
