"""Verificación de outputs locales de ComfyUI sin red ni inferencia."""
import json
import re
import struct
import zlib

LIMIT=16*1024*1024


def png_prompt(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Salida PNG inválida.")
    offset=8
    prompt=None
    complete=False
    while offset+12<=len(data):
        length=struct.unpack(">I",data[offset:offset+4])[0]
        end=offset+12+length
        if length>LIMIT or end>len(data):
            raise ValueError("PNG truncado.")
        kind=data[offset+4:offset+8]
        payload=data[offset+8:offset+8+length]
        checksum=struct.unpack(">I",data[offset+8+length:end])[0]
        if zlib.crc32(kind+payload)&0xffffffff!=checksum:
            raise ValueError("CRC del PNG incorrecto.")
        if kind==b"tEXt" and payload.startswith(b"prompt\0"):
            if prompt is not None:
                raise ValueError("Metadata PNG ambigua.")
            prompt=json.loads(payload.split(b"\0",1)[1])
        offset=end
        if kind==b"IEND":
            complete=length==0 and offset==len(data)
            break
    if prompt is None or not complete:
        raise ValueError("Falta metadata de workflow en PNG.")
    return prompt


def graph_matches(actual,expected,reference_sha256=None):
    if not isinstance(actual,dict) or set(actual)!=set(expected):
        return False
    normalized={}
    for key,node in actual.items():
        if not isinstance(node,dict):
            return False
        entry=dict(node)
        if "is_changed" in entry:
            if entry.get("class_type")!="LoadImage" or entry["is_changed"]!=[reference_sha256]:
                return False
            entry.pop("is_changed")
        normalized[key]=entry
    return equivalent(normalized,expected)


def equivalent(a,b):
    if isinstance(a,bool) or isinstance(b,bool):
        return type(a) is type(b) and a==b
    if isinstance(a,dict) and isinstance(b,dict):
        return set(a)==set(b) and all(equivalent(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return a==b
    return type(a) is type(b) and a==b


def output_file(root,operation):
    folder=(root/"ComfyUI/output").resolve()
    extension=".png" if operation["kind"]=="reference" else ".mp4"
    prefix="studio_"+operation["id"]
    candidates=[]
    for path in folder.glob(prefix+"*"+extension):
        if re.fullmatch(re.escape(prefix)+r"_\d+_"+re.escape(extension),path.name):
            if path.is_symlink() or not path.is_file() or path.resolve().parent!=folder:
                raise ValueError("La salida local no es un archivo regular del proveedor.")
            if path.stat().st_size>LIMIT:
                raise ValueError("La salida local excede el límite.")
            candidates.append(path)
            if len(candidates)>1:
                raise ValueError("Varias salidas locales para el mismo ID; requiere conciliación manual.")
    return candidates[0] if candidates else None


def metadata_matches(path,probe,operation,reference_sha256):
    if path.stat().st_size>LIMIT:
        raise ValueError("La salida local excede el límite.")
    if operation["kind"]=="reference":
        graph=png_prompt(path.read_bytes())
    else:
        text=probe.get("format",{}).get("tags",{}).get("prompt")
        if not text:
            raise ValueError("Falta metadata de workflow en MP4.")
        graph=json.loads(text)
    if not graph_matches(graph,operation["graph"],reference_sha256):
        raise ValueError("El grafo o la referencia de la salida no coincide con la petición persistida.")
