import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    data: Path
    port: int
    backend: str
    socket: str
    home_root: Path | None = None

    @classmethod
    def load(cls):
        profile=os.getenv("STUDIO_PROFILE", "work")
        if profile not in ("work","home16"):
            raise ValueError("STUDIO_PROFILE debe ser work o home16.")
        port = int(os.getenv("STUDIO_PORT", "8765"))
        if not 1 <= port <= 65535:
            raise ValueError("STUDIO_PORT debe estar entre 1 y 65535.")
        backend = os.getenv("STUDIO_DB", "sqlite")
        if backend not in ("sqlite", "postgres"):
            raise ValueError("STUDIO_DB debe ser sqlite o postgres.")
        socket = os.getenv("STUDIO_PG_SOCKET", "/var/run/postgresql")
        if not PurePosixPath(socket).is_absolute() or "," in socket:
            raise ValueError("STUDIO_PG_SOCKET debe ser una ruta de socket Unix.")
        data = Path(os.getenv("STUDIO_DATA", ".studio")).expanduser()
        home_root = None
        if os.getenv("STUDIO_ENABLE_HOME", "0") == "1":
            if profile != "home16":
                raise ValueError("WORK bloquea inferencia; HOME requiere STUDIO_PROFILE=home16.")
            value = os.getenv("STUDIO_HOME_ROOT", "")
            if not value or not Path(value).is_absolute():
                raise ValueError("HOME requiere STUDIO_HOME_ROOT absoluto.")
            home_root = Path(value).resolve()
        elif profile == "home16":
            raise ValueError("HOME requiere opt-in STUDIO_ENABLE_HOME=1.")
        return cls((ROOT / data).resolve(), port, backend, socket, home_root)
