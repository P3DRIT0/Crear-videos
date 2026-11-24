"""Operación Windows de instalaciones locales. Nunca instala ni descarga al arrancar."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import psutil

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from packages.local_lock import exclusive_file


def environment(root, allow_downloads=False):
    env = dict(os.environ)
    ffmpeg = root / "ffmpeg/ffmpeg-9.1-essentials_build/bin"
    env.update(PYTHONUTF8="1", STUDIO_PROFILE="home16", STUDIO_DB="sqlite", STUDIO_ENABLE_HOME="1",
               STUDIO_HOME_ROOT=str(root),
               STUDIO_DATA=str(root / "data"), STUDIO_PORT="8765",
               OLLAMA_HOST="127.0.0.1:11434", OLLAMA_MODELS=str(root / "models/ollama"),
               OLLAMA_NO_CLOUD="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1",
               OLLAMA_KEEP_ALIVE="0", OLLAMA_CONTEXT_LENGTH="2048",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               HF_HOME=str(root / "cache/huggingface"), DO_NOT_TRACK="1",
               TEMP=str(root / "tmp"), TMP=str(root / "tmp"),
               PATH=str(ffmpeg) + os.pathsep + str(root / "ollama") + os.pathsep + env.get("PATH", ""))
    for key in ("http_proxy","https_proxy","all_proxy","no_proxy"):
        env.pop(key,None)
    if allow_downloads:
        for key in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"):
            env.pop(key,None)
    else:
        env.update(HTTP_PROXY="http://127.0.0.1:8767",HTTPS_PROXY="http://127.0.0.1:8767",ALL_PROXY="http://127.0.0.1:8767")
    env["NO_PROXY"]="127.0.0.1,localhost,::1"
    return env


def definitions(root):
    return {
        "network": ([str(root/"venvs/studio/Scripts/python.exe"),"-u","-m","apps.api.network_guard"],REPO,8767,"/health"),
        "ollama": ([str(root / "ollama/ollama.exe"), "serve"], root, 11434, "/api/version"),
        "comfy": ([str(root / "venvs/comfy/Scripts/python.exe"), "-u",str(REPO/"scripts/comfy-offline.py"),"--root",str(root/"ComfyUI"), "--listen", "127.0.0.1",
                   "--port", "8188", "--disable-auto-launch", "--disable-all-custom-nodes", "--offline",
                   "--preview-method", "none", "--reserve-vram", "1.5", "--fast-disk"], root / "ComfyUI", 8188, "/system_stats"),
        "studio": ([str(root / "venvs/studio/Scripts/python.exe"), "-u", "-m", "apps.api.server"], REPO, 8765, "/api/v1/health"),
    }


def request(port, path):
    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
        return json.load(response)


def read_state(root):
    path = root / "run/processes.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def owned(record):
    try:
        process = psutil.Process(record["pid"])
        if abs(process.create_time() - record["created"]) < 0.1 and process.cmdline() == record["cmdline"]:
            return process
    except (psutil.Error, KeyError):
        pass
    return None


def save_state(root, state):
    path = root / "run/processes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(state,stream,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def start(root, names, allow_downloads=False):
    state = read_state(root)
    for name in names:
        args, cwd, port, health = definitions(root)[name]
        if name in state and owned(state[name]):
            if state[name]["cmdline"]!=args or state[name].get("downloads_allowed",False)!=(allow_downloads and name=="ollama"):
                raise RuntimeError(name+": configuración distinta; deténgalo antes de arrancar con la nueva configuración.")
            request(port, health)
            print(f"{name}: ya operativo en 127.0.0.1:{port}", flush=True)
            continue
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Puerto {port} ocupado por un proceso no gestionado; no se modifica.")
        if not Path(args[0]).is_file():
            raise RuntimeError("Falta instalación: " + args[0])
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "tmp").mkdir(exist_ok=True)
        with (root / f"logs/{name}-out.log").open("ab") as out, (root / f"logs/{name}-err.log").open("ab") as err:
            child = subprocess.Popen(args, cwd=cwd, env=environment(root,allow_downloads and name=="ollama"), stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=err,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        process = psutil.Process(child.pid)
        state[name] = {"pid": child.pid, "created": process.create_time(), "cmdline": process.cmdline(),
                       "downloads_allowed":allow_downloads and name=="ollama"}
        save_state(root, state)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"{name} terminó con código {child.returncode}. Consulte {root / 'logs'}.")
            try:
                request(port, health)
                print(f"{name}: operativo en http://127.0.0.1:{port}", flush=True)
                break
            except (OSError, ValueError):
                time.sleep(0.5)
        else:
            raise TimeoutError(f"{name}: arranque no confirmado; consulte los logs y use stop.")


def stop(root, names):
    state = read_state(root)
    for name in reversed(names):
        record = state.get(name)
        process = owned(record) if record else None
        if process:
            # Los venv Windows tienen un lanzador padre y un intérprete hijo.
            children = process.children(recursive=True)
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
            _, alive = psutil.wait_procs([process, *children], timeout=8)
            if alive:
                raise RuntimeError(f"{name}: proceso aún activo; no se fuerza su terminación.")
        state.pop(name, None)
        save_state(root, state)
        print(f"{name}: detenido o sin proceso gestionado", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "test", "inspect", "prepare", "benchmark", "reel"])
    parser.add_argument("service", nargs="?", choices=["all", "studio", "ollama", "comfy","network"], default="all")
    parser.add_argument("--allow-downloads",action="store_true",help="Solo instalación: start ollama con descargas explícitas; no permite producción.")
    parser.add_argument("--root", type=Path, default=Path(os.getenv("STUDIO_HOME_ROOT", "E:/AI-Creative-Studio")))
    parser.add_argument("--stage", choices=["script", "image", "clip"], default="script")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.allow_downloads and (args.action!="start" or args.service!="ollama"):
        parser.error("--allow-downloads solo se admite con start ollama.")
    names = list(definitions(root)) if args.service == "all" else [args.service]
    env = environment(root)
    if args.action == "start":
        (root/"run").mkdir(parents=True,exist_ok=True)
        with exclusive_file(root/"run/manager.lock"):
            start(root, names,args.allow_downloads)
    elif args.action == "stop":
        (root/"run").mkdir(parents=True,exist_ok=True)
        with exclusive_file(root/"run/manager.lock"):
            stop(root, names)
    elif args.action == "status":
        state = read_state(root)
        failed = False
        for name in names:
            _, _, port, path = definitions(root)[name]
            try:
                data = request(port, path)
                detail = data if name != "comfy" else data.get("system", {})
                print(json.dumps({"service": name, "port": port, "managed": bool(owned(state.get(name, {}))), "health": detail}))
            except (OSError, ValueError) as exc:
                print(f"{name}: no disponible ({exc})")
                failed = True
        if failed:
            raise SystemExit(1)
    elif args.action == "test":
        subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO, env=env, check=True)
        for filename in ("app.js", "studio.js"):
            subprocess.run(["node", "--check", str(REPO / "apps/dashboard" / filename)], check=True)
    elif args.action == "inspect":
        subprocess.run([sys.executable, str(REPO / "scripts/home-inspect.py")], cwd=root, env=env, check=True)
    elif args.action == "prepare":
        from integrations.home_setup import prepare
        prepare(root)
    elif args.action == "benchmark":
        output = root / "benchmarks" / (args.stage + "-" + time.strftime("%Y%m%d-%H%M%S"))
        subprocess.run([sys.executable, "-m", "integrations.home", str(root / "manifests" / (args.stage + ".json")), str(output)],
                       cwd=REPO, env=env, check=True)
        print(output)
    elif args.action == "reel":
        subprocess.run([sys.executable, "-m", "integrations.home_reel", str(root)], cwd=REPO, env=env, check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
