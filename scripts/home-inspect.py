"""Inventario de solo lectura para ejecutar en el equipo de destino."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def memory():
    if Path("/proc/meminfo").is_file():
        line=next(v for v in Path("/proc/meminfo").read_text().splitlines() if v.startswith("MemTotal:"))
        return round(int(line.split()[1])/1024**2,1)
    if os.name=="nt":
        import ctypes
        from ctypes import wintypes
        class Memory(ctypes.Structure):
            _fields_=[("length",wintypes.DWORD),("load",wintypes.DWORD)]+[
                (n,ctypes.c_ulonglong) for n in ("total","avail","page","free_page","virtual","free_virtual","extended")]
        data=Memory()
        data.length=ctypes.sizeof(data)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data)):
            return round(data.total/1024**3,1)
    return None


def inspect():
    gpu=None
    if shutil.which("nvidia-smi"):
        result=subprocess.run(["nvidia-smi","--query-gpu=name,driver_version,memory.total,memory.free",
                               "--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=15)
        if result.returncode==0:
            gpu=result.stdout.strip().splitlines()
    return {"os":platform.platform(),"ram_gib":memory(),"disk_free_gib":round(shutil.disk_usage(".").free/1024**3,1),
            "gpu_name_driver_total_free_mib":gpu,"executables":{k:bool(shutil.which(k)) for k in ("ffmpeg","ffprobe","ollama","nvidia-smi")}}

if __name__=="__main__":
    print(json.dumps(inspect(),indent=2,ensure_ascii=False))
