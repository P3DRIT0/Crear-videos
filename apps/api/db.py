import os
import sqlite3
from contextlib import contextmanager

from .config import ROOT


class Database:
    def __init__(self, config):
        self.config = config
        self.pg = config.backend == "postgres"

    @contextmanager
    def transaction(self, write=False):
        if self.pg:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("Falta psycopg 3. Use STUDIO_DB=sqlite en WORK.") from exc
            if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE"):
                raise ValueError("Desactive PGHOSTADDR y PGSERVICE para usar el socket local.")
            conn = psycopg.connect(dbname="creative_studio", host=self.config.socket,
                                   port=5432, connect_timeout=5, row_factory=dict_row,
                                   options="-c statement_timeout=5000 -c lock_timeout=5000")
        else:
            conn = sqlite3.connect(self.config.data / "studio.sqlite3", timeout=5)
            conn.row_factory = sqlite3.Row
        try:
            if not self.pg:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")

            def execute(sql, args=()):
                return conn.execute(sql.replace("?", "%s") if self.pg else sql, args)

            yield execute
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        self.config.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction(write=True) as query:
            if self.pg:
                query("SELECT pg_advisory_xact_lock(8411001)")
            query("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
            versions = [row["version"] for row in query("SELECT version FROM schema_version ORDER BY version")]
            migrations = ["001_core", "002_production", "003_models", "004_policy"]
            if versions != list(range(1, len(versions) + 1)) or len(versions) > len(migrations):
                raise RuntimeError("Versión de esquema incompatible.")
            for name in migrations[len(versions):]:
                migration = ROOT / "infra/migrations" / (name + ".up.sql")
                for statement in migration.read_text().split(";"):
                    if statement.strip():
                        query(statement)
