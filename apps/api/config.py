import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    data: Path
    port: int
    backend: str
    socket: str

    @classmethod
    def load(cls):
        if os.getenv("STUDIO_PROFILE", "work") != "work":
            raise ValueError("Esta versión solo admite STUDIO_PROFILE=work.")
        port = int(os.getenv("STUDIO_PORT", "8765"))
        if not 1 <= port <= 65535:
            raise ValueError("STUDIO_PORT debe estar entre 1 y 65535.")
        backend = os.getenv("STUDIO_DB", "sqlite")
        if backend not in ("sqlite", "postgres"):
            raise ValueError("STUDIO_DB debe ser sqlite o postgres.")
        socket = os.getenv("STUDIO_PG_SOCKET", "/var/run/postgresql")
        if not Path(socket).is_absolute() or "," in socket:
            raise ValueError("STUDIO_PG_SOCKET debe ser una ruta de socket Unix.")
        data = Path(os.getenv("STUDIO_DATA", ".studio")).expanduser()
        return cls((ROOT / data).resolve(), port, backend, socket)
