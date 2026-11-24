import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from .db import Database
from .executor import ManualBriefExecutor
from .storage import BlobStore, canonical


class Problem(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def one(cursor, subject):
    row = cursor.fetchone()
    if row is None:
        raise Problem(404, "missing", f"{subject}: registro no encontrado.")
    return dict(row)


class Studio:
    def __init__(self, config):
        self.db = Database(config)
        self.db.initialize()
        self.blobs = BlobStore(config.data)
        self.executor = ManualBriefExecutor(self.blobs)

    def health(self):
        with self.db.transaction() as query:
            version = one(query("SELECT MAX(version) AS version FROM schema_version"), "Esquema")["version"]
            if version != 4:
                raise RuntimeError("Versión de esquema incorrecta.")
            self.blobs.check()
        return {"status": "ok", "database": self.db.config.backend,
                "schema_version": version, "storage": "ok"}

    def capabilities(self):
        return {"profile": "work", "database": self.db.config.backend, "gpu_jobs": 0,
                "remote_inference": False, "publishing": False, "executor": self.executor.name}

    def brands(self):
        with self.db.transaction() as query:
            return [dict(row) for row in query("SELECT * FROM brands ORDER BY name, id")]

    def scoped(self, method, brand, collection, item=None, action=None, body=None, key=None):
        # collection is selected by the route table, never interpolated from free text.
        assert collection in ("campaigns", "jobs")
        write = method != "GET"
        with self.db.transaction(write=write) as query:
            lock = " FOR UPDATE" if write and self.db.pg else ""
            owner = one(query("SELECT * FROM brands WHERE id=?" + lock, (brand,)), "Marca")
            if item is None:
                if method == "GET":
                    return [dict(row) for row in query(
                        f"SELECT * FROM {collection} WHERE brand_id=? ORDER BY created_at DESC, id",
                        (brand,))]
                return self.create(query, brand, collection, body, key)

            row = one(query(f"SELECT * FROM {collection} WHERE brand_id=? AND id=?", (brand, item)),
                      "Campaña" if collection == "campaigns" else "Job")
            if action == "run":
                return self.run(query, owner, row)
            if action == "artifact":
                if row["state"] != "succeeded":
                    raise Problem(409, "pending_artifact", "Ejecute el job para obtener la ficha.")
                return self.blobs.read(row["sha256"])
            if method == "GET":
                return row
            if method == "DELETE":
                if collection == "campaigns" and query(
                    "SELECT id FROM productions WHERE brand_id=? AND campaign_id=?", (brand, item)
                ).fetchone():
                    raise Problem(409, "production_exists", "La campaña conserva producciones.")
                if collection == "campaigns" and query(
                    "SELECT id FROM jobs WHERE brand_id=? AND campaign_id=?", (brand, item)
                ).fetchone():
                    raise Problem(409, "campaign_in_use", "Elimine primero los jobs de la campaña.")
                query(f"DELETE FROM {collection} WHERE brand_id=? AND id=?", (brand, item))
                return None
            if collection == "jobs" and row["state"] != "pending":
                raise Problem(409, "locked_job", "Solo puede editar un job pendiente.")
            fields = ", ".join(f"{field}=?" for field in body)
            query(f"UPDATE {collection} SET {fields} WHERE brand_id=? AND id=?",
                  (*body.values(), brand, item))
            return row | body

    def create(self, query, brand, collection, body, key):
        fingerprint = hashlib.sha256(canonical([collection, body])).hexdigest()
        previous = query("SELECT fingerprint,response FROM creations WHERE brand_id=? AND request_key=?",
                         (brand, key)).fetchone()
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise Problem(409, "key_conflict", "Esta clave ya identifica otra petición.")
            return json.loads(previous["response"])
        row = dict(id=str(uuid4()), brand_id=brand, created_at=datetime.now(UTC).isoformat(), **body)
        if collection == "jobs":
            one(query("SELECT id FROM campaigns WHERE brand_id=? AND id=?",
                      (brand, body["campaign_id"])), "Campaña")
            row.update(state="pending", sha256=None, error=None)
        fields = ", ".join(row)
        params = ", ".join("?" for _ in row)
        query(f"INSERT INTO {collection} ({fields}) VALUES ({params})", tuple(row.values()))
        query("INSERT INTO creations (brand_id,request_key,fingerprint,response) VALUES (?,?,?,?)",
              (brand, key, fingerprint, json.dumps(row)))
        return row

    def run(self, query, brand, job):
        if job["state"] == "succeeded":
            return job
        campaign = one(query("SELECT * FROM campaigns WHERE id=? AND brand_id=?",
                             (job["campaign_id"], brand["id"])), "Campaña")
        try:
            digest = self.executor.execute(brand, campaign)
            job.update(state="succeeded", sha256=digest, error=None)
        except OSError:
            job.update(state="failed", sha256=None,
                       error="No se pudo guardar la ficha. Compruebe el espacio y los permisos.")
        query("UPDATE jobs SET state=?,sha256=?,error=? WHERE id=? AND brand_id=?",
              (job["state"], job["sha256"], job["error"], job["id"], brand["id"]))
        return job
