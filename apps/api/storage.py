import hashlib
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


class BlobStore:
    def __init__(self, root):
        self.root = root / "blobs"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def path(self, digest):
        if not re.fullmatch("[a-f0-9]{64}", digest):
            raise ValueError("Hash inválido.")
        return self.root / digest

    def save(self, content):
        digest = hashlib.sha256(content).hexdigest()
        target = self.path(digest)
        temp = NamedTemporaryFile(dir=self.root, delete=False)
        path = Path(temp.name)
        try:
            with temp:
                temp.write(content)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(path, target)
            if hasattr(os, "O_DIRECTORY"):
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            path.unlink(missing_ok=True)
        return digest

    def read(self, digest):
        data = self.path(digest).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise OSError("El contenido de la ficha no coincide con su hash.")
        return data

    def check(self):
        with NamedTemporaryFile(dir=self.root) as probe:
            probe.write(b"health")
            probe.flush()
