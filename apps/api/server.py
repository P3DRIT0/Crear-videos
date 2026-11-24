import argparse
import json
import os
import re
import sys
import time
from threading import Event, Thread
from .production import ProductionService
from .worker import loop
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID
from urllib.parse import parse_qs, urlsplit

from pydantic import TypeAdapter, ValidationError
from packages.contracts.routes import PREFIX, ROUTES, openapi
from .config import Config, ROOT
from .service import Problem, Studio
from .storage import canonical


STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/studio": ("studio.html", "text/html; charset=utf-8"),
          "/studio.js": ("studio.js", "text/javascript; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
PATTERNS = [(re.compile(PREFIX + r.path.replace("{brand}", "(?P<brand>[^/]+)")
                        .replace("{item}", "(?P<item>[^/]+)").replace("{digest}", "(?P<digest>[0-9a-f]{64})")), r) for r in ROUTES]


@lru_cache
def body_adapter(model):
    return TypeAdapter(model)


def uuid_text(value):
    try:
        result = str(UUID(value))
        if result != value:
            raise ValueError
        return result
    except (TypeError, ValueError, AttributeError):
        raise Problem(422, "invalid_id", "Se requiere un UUID canónico.") from None


class Handler(BaseHTTPRequestHandler):
    timeout = 10

    def log_message(self, fmt, *args):
        pass  # Only log route-independent metadata. Never log operator inputs or URLs.

    def dispatch(self):
        try:
            port = self.server.server_port
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if port == 80:
                allowed.update(("127.0.0.1", "localhost"))
            host = self.headers.get("Host")
            if host not in allowed or self.headers.get("Origin", f"http://{host}") != f"http://{host}":
                raise Problem(403, "local_only", "Se requiere el origen local del estudio.")
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise Problem(403, "local_only", "La petición debe proceder del estudio.")
            path = self.path.partition("?")[0]
            if self.command == "GET" and path in STATIC:
                filename, mime = STATIC[path]
                return self.respond(200, (ROOT / "apps/dashboard" / filename).read_bytes(), mime)
            if self.command == "GET" and path == PREFIX + "/openapi.json":
                return self.respond(200, self.server.spec)
            allowed_methods = []
            for pattern, route in PATTERNS:
                match = pattern.fullmatch(path)
                if not match:
                    continue
                allowed_methods.append(route.method)
                if route.method != self.command:
                    continue
                ids = {k: (v if k=="digest" else uuid_text(v)) for k, v in match.groupdict().items()}
                body = self.parse_body(route.body)
                key = uuid_text(self.headers.get("Idempotency-Key")) if route.key else None
                studio = self.server.studio
                if route.path=="/brands" and route.method=="POST":
                    result=self.server.production.new_brand(body,key)
                elif route.path.startswith("/brands/{brand}/") and route.path.split("/")[3] not in ("campaigns","jobs"):
                    parts=route.path.split("/")
                    action=parts[5] if len(parts)>5 else None
                    if action=="events":
                        return self.events(ids["brand"],ids["item"])
                    result=self.server.production.dispatch(route.method,ids["brand"],parts[3],ids.get("item"),
                                                           action,body,key,ids.get("digest"))
                    if action=="assets":
                        return self.media_response(*result)
                elif not ids:
                    call = {"/health": studio.health, "/brands": studio.brands,
                            "/system/capabilities": studio.capabilities}[route.path]
                    result = call()
                else:
                    parts = route.path.split("/")
                    result = studio.scoped(route.method, ids["brand"], parts[3], ids.get("item"),
                                           parts[5] if len(parts) == 6 else None, body, key)
                data = result if isinstance(result, bytes) else canonical(result)
                return self.respond(route.status, b"" if route.status == 204 else data)
            if allowed_methods:
                raise Problem(405, "method", "Método no permitido para este recurso.")
            raise Problem(404, "missing", "Ruta no encontrada.")
        except Problem as exc:
            self.respond(exc.status, canonical({"code": exc.code, "message": str(exc)}))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            print(json.dumps({"event": "service_error", "exception": type(exc).__name__}),
                  file=sys.stderr, flush=True)
            self.respond(503, canonical({"code": "unavailable",
                                       "message": "Recurso local no disponible. Revise el disco y la base."}))

    def events(self, brand, item):
        try:
            query=parse_qs(urlsplit(self.path).query,keep_blank_values=True,max_num_fields=1)
            if set(query)-{"after"} or len(query.get("after",["0"]))!=1:
                raise ValueError
            value=self.headers.get("Last-Event-ID",query.get("after",["0"])[0])
            if not re.fullmatch(r"\d{1,19}",value):
                raise ValueError
            cursor=int(value)
            if cursor>2**63-1:
                raise ValueError
        except ValueError:
            raise Problem(422,"cursor","Cursor SSE inválido.") from None
        with self.server.studio.db.transaction() as q:
            if not q("SELECT id FROM productions WHERE brand_id=? AND id=?",(brand,item)).fetchone():
                raise Problem(404,"missing","Producción desconocida.")
        self.send_response(200)
        self.send_header("Content-Type","text/event-stream")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(b"retry: 1000\n\n")
        for _ in range(12):
            with self.server.studio.db.transaction() as q:
                rows=q("SELECT revision,message FROM production_events WHERE production_id=? AND revision>? "
                       "ORDER BY revision",(item,cursor)).fetchall()
            for row in rows:
                cursor=row["revision"]
                self.wfile.write(f"id: {cursor}\ndata: ".encode()+canonical(dict(row))+b"\n\n")
            self.wfile.flush()
            time.sleep(0.5)

    def parse_body(self, model):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise Problem(400, "length", "Longitud inválida.") from None
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) > 1:
            raise Problem(400, "length", "Codificación de cuerpo no admitida.")
        if size < 0 or size > 16384:
            raise Problem(413, "size", "El límite por petición es de 16 KiB.")
        if model is None:
            if size:
                raise Problem(400, "body", "Esta operación no admite cuerpo.")
            return None
        if self.headers.get_content_type() != "application/json":
            raise Problem(415, "mime", "Envíe application/json.")
        try:
            adapter = body_adapter(model)
            return adapter.dump_python(adapter.validate_json(self.rfile.read(size)), mode="json", by_alias=True)
        except ValidationError as exc:
            fields = [str(error["loc"][0]) for error in exc.errors() if error["loc"]]
            detail = ", ".join(fields) or "JSON"
            raise Problem(422, "validation", f"Revise los campos de la petición ({detail}).") from None

    def media_response(self,data,mime):
        header=self.headers.get("Range")
        if not header:
            return self.respond(200,data,mime,{"Accept-Ranges":"bytes"})
        match=re.fullmatch(r"bytes=(\d*)-(\d*)",header)
        length=len(data)
        if match and (match[1] or match[2]):
            start=int(match[1]) if match[1] else max(0,length-int(match[2]))
            end=min(length-1,int(match[2])) if match[1] and match[2] else length-1
            if 0<=start<=end<length:
                return self.respond(206,data[start:end+1],mime,{"Accept-Ranges":"bytes",
                                    "Content-Range":f"bytes {start}-{end}/{length}"})
        return self.respond(416,b"",mime,{"Content-Range":f"bytes */{length}"})

    def respond(self, status, data, mime="application/json; charset=utf-8",headers=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        for name,value in (headers or {}).items():
            self.send_header(name,value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; "
                         "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = dispatch


def build_server(config, port=None):
    studio = Studio(config)
    server = ThreadingHTTPServer(("127.0.0.1", config.port if port is None else port), Handler)
    server.studio = studio
    server.production = ProductionService(studio)
    server.spec = canonical(openapi())
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    config = Config.load()
    from packages.network_policy import install
    install()
    if args.check:
        print(json.dumps(Studio(config).health()))
        return
    with build_server(config) as server:
        print(f"AI Creative Studio · http://127.0.0.1:{server.server_port}", flush=True)
        stop = Event()
        worker = Thread(target=loop,args=(server.studio,stop),daemon=True)
        worker.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            worker.join(timeout=1)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        sys.exit(str(error))
