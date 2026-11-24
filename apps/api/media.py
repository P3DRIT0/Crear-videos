"""Material geométrico original de WORK; todos los productos llevan la marca MOCK."""
import array
from contextvars import ContextVar
import hashlib
import json
import math
from pathlib import Path
import random
import re
import struct
import subprocess
import time
import unicodedata
import wave
import zlib

from .storage import canonical

# Alfabeto bitmap original, cinco filas de tres bits.
GLYPHS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", (
    "25755","65656","34443","65556","74647","74644","34553","55755","72227",
    "11152","55655","44447","57755","57775","25552","65644","25573","65655",
    "34216","72222","55557","55552","55775","55255","55222","71247",
    "75557","26227","71247","71217","55711","74617","74657","71111","75757","75717")))
MEDIA_LICENSE = "original-procedural-v1"
REAL_LICENSE = "verified-local-generation-v1"
RENDERER = "pixel-work/2"
RENDERER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def rgb(value):
    return bytes.fromhex(value.lstrip("#"))


class Raster:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.pixels = bytearray(color * w * h)

    def rect(self, x, y, w, h, color):
        left, right = max(0, x), min(self.w, x+w)
        if right <= left:
            return
        for row in range(max(0, y), min(self.h, y+h)):
            start = (row*self.w+left)*3
            self.pixels[start:start+(right-left)*3] = color*(right-left)

    def text(self, value, y, color, scale=1):
        letters = unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().upper()
        letters = letters[:self.w//(4*scale)]
        x = (self.w-(len(letters)*4-1)*scale)//2
        for letter in letters:
            for row, bits in enumerate(GLYPHS.get(letter, "")):
                for col in range(3):
                    if int(bits) & (4 >> col):
                        self.rect(x+col*scale,y+row*scale,scale,scale,color)
            x += 4*scale

    def png(self):
        def chunk(kind, data):
            return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
        lines = b"".join(b"\0"+self.pixels[i:i+self.w*3] for i in range(0,len(self.pixels),self.w*3))
        return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",self.w,self.h,8,2,0,0,0))
                +chunk(b"IDAT",zlib.compress(lines))+chunk(b"IEND",b""))


def sprite(character, view="front"):
    pic = Raster(16,16,rgb("00ff00"))
    color = rgb(character["color"])
    if character.get("shape")=="cursor":
        for y in range(12):
            pic.rect(2,1+y,min(9,y+1),1,color)
        pic.rect(7,10,3,5,color)
    elif character.get("shape")=="orb":
        for y in range(12):
            half=int(math.sqrt(max(0,36-(y-6)**2)))
            pic.rect(8-half,2+y,2*half,1,color)
    else:
        pic.rect(3,4,10,9,color)
    pic.rect(5,2,6,2,color)
    pic.rect(3,13,3,2,color)
    pic.rect(10,13,3,2,color)
    if view!="back":
        eye=8 if view=="side" else 5
        pic.rect(eye,6,5 if view=="front" else 3,3,rgb("1f2231"))
        pic.rect(eye+2,6,2,2,rgb("ffffdf"))
    else:
        pic.rect(6,7,4,3,rgb("6a5364"))
    return pic.png()


def backdrop(doc, shot, attempt):
    pic = Raster(135,240,rgb(doc["preset"]["background"]))
    seed = int.from_bytes(hashlib.sha256(canonical([shot,attempt])).digest()[:8],"big")
    rng = random.Random(seed)
    accent = rgb(doc["preset"]["accent"])
    for _ in range(85):
        pic.rect(rng.randrange(135),rng.randrange(145),1,1,rgb("beb8d9"))
    for radius in range(28,0,-1):
        for dy in range(-radius,radius+1):
            dx = int(math.sqrt(radius*radius-dy*dy))
            shade = bytes(max(1,v*(48-radius)//62) for v in accent)
            pic.rect(67-dx,83+dy,2*dx+1,1,shade)
    for x in range(0,135,5):
        h=rng.randint(3,18)
        pic.rect(x,147-h,4,h,rgb("423851"))
    for offset in range(-7,8):
        for y in range(147,240):
            pic.rect(int(67+offset*(y-144)/4),y,1,1,rgb("55415c"))
    for y in (148,151,157,166,180,198,223):
        pic.rect(0,y,135,1,rgb("55415c"))
    pic.text("MOCK",18,rgb("fff2cc"),2)
    pic.text(doc["brand_name"] if shot["order"] >= 4 else doc["title"].split(" · ")[-1],
             165,rgb("fff2cc"),2)
    pic.text(f"PLANO {shot['order']}  V{attempt+1}",206,accent)
    return pic.png()


cancellation_check = ContextVar("cancellation_check",default=lambda:False)


def command(args, cwd, timeout=100):
    try:
        proc=subprocess.Popen(args,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Falta {args[0]} en PATH.") from exc
    deadline=time.monotonic()+timeout
    with proc:
        try:
            while True:
                try:
                    stdout,stderr=proc.communicate(timeout=0.4)
                    break
                except subprocess.TimeoutExpired:
                    if cancellation_check.get()():
                        raise RuntimeError("Render cancelado.")
                    if time.monotonic()>=deadline:
                        raise RuntimeError(f"{args[0]} superó {timeout} segundos.")
        except BaseException:
            proc.kill()
            proc.communicate()
            raise
    if proc.returncode:
        raise RuntimeError(f"{args[0]}: "+stderr.decode(errors="replace")[-400:])
    return subprocess.CompletedProcess(args,proc.returncode,stdout,stderr)


def encode(args, work):
    return command(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
                    "-filter_complex_threads","1",*args],work)


def asset(store, data, mime, *, simulated=True, provenance=None):
    result = {"sha256":store.save(data),"mime":mime,"bytes":len(data),
              "simulated":simulated,"license":MEDIA_LICENSE if simulated else REAL_LICENSE}
    if not simulated:
        if not provenance:
            raise ValueError("Falta procedencia de la generación real.")
        result.update(license_verified=True, provenance=provenance)
    return result


def input_hash(doc, index):
    shot = doc["plan"]["shots"][index]
    material = shot
    if doc.get("provider") == "home-local-v1":
        material = [shot, doc["home"]["epoch"], doc["character"]["reference"]["sha256"]]
    return hashlib.sha256(canonical(material)).hexdigest()


def licensed(entry, simulated):
    if simulated:
        return entry.get("simulated") is True and entry.get("license") == MEDIA_LICENSE
    return (entry.get("simulated") is False and entry.get("license") == REAL_LICENSE
            and entry.get("license_verified") is True and bool(entry.get("provenance")))


def render_shot(doc, index, store, work):
    start=time.monotonic()
    shot=doc["plan"]["shots"][index]
    attempt=doc["attempts"][index]
    (work/"background.png").write_bytes(backdrop(doc,shot,attempt))
    (work/"sprite.png").write_bytes(sprite(doc["character"]))
    light=Raster(7,7,rgb("00ff00"))
    light.rect(2,0,3,7,rgb(doc["preset"]["accent"]))
    light.rect(0,2,7,3,rgb(doc["preset"]["accent"]))
    light.rect(2,2,3,3,rgb("fff4cf"))
    (work/"light.png").write_bytes(light.png())
    phase=(shot["seed"]%12+attempt*7+index)/3
    graph=(f"[1:v]colorkey=0x00ff00:0.01:0[char];[2:v]colorkey=0x00ff00:0.01:0[light];"
           f"[0:v][light]overlay=x='72+37*sin(t*1.5+{phase}+0.45)':y='101+13*cos(t*2+{phase}+0.45)'[scene];"
           f"[scene][char]overlay="
           f"x='59+37*sin(t*1.5+{phase})':y='106+13*cos(t*2+{phase})',"
           "scale=360:640:flags=neighbor,setsar=1,format=yuv420p[v]")
    encode(["-loop","1","-framerate","24","-i","background.png","-loop","1","-framerate","24",
            "-i","sprite.png","-loop","1","-framerate","24","-i","light.png","-filter_complex",graph,"-map","[v]","-t",str(shot["duration"]),
            "-c:v","libx264","-preset","veryfast","-threads","2","-crf","19","shot.mp4"],work)
    clip=asset(store,(work/"shot.mp4").read_bytes(),"video/mp4")
    return clip | {"order":index+1,"candidate":attempt+1,"seed":shot["seed"],"renderer":RENDERER,
                   "duration":shot["duration"],"seconds_elapsed":round(time.monotonic()-start,3),
                   "input_hash":hashlib.sha256(canonical(shot)).hexdigest()}


def sound(timeline, target, score):
    rate=score["sample_rate"]
    with wave.open(str(target),"wb") as out:
        out.setparams((1,2,rate,0,"NONE","not compressed"))
        for i,entry in enumerate(timeline):
            samples=array.array("h")
            frequency=score["frequencies_hz"][i]
            for j in range(rate*entry["duration"]):
                t=j/rate
                envelope=min(1,t*12,(entry["duration"]-t)*8)*math.exp(-3*(t%0.5))
                samples.append(int(3400*envelope*math.sin(math.tau*frequency*t)))
            if struct.pack("=H",1)!=struct.pack("<H",1):
                samples.byteswap()
            out.writeframes(samples.tobytes())


def inspect_video(path, duration):
    result=command(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)],path.parent)
    data=json.loads(result.stdout)
    video=next(s for s in data["streams"] if s["codec_type"]=="video")
    audio=next(s for s in data["streams"] if s["codec_type"]=="audio")
    analysis=command(["ffmpeg","-hide_banner","-nostdin","-threads","2","-i",str(path),
                      "-vf","scale=180:320,blackdetect=d=0.1:pix_th=0.05","-af","volumedetect",
                      "-f","null","-"],path.parent).stderr.decode(errors="replace")
    peak=re.search(r"max_volume: ([-.\d]+) dB",analysis)
    qc={"width":video["width"],"height":video["height"],"fps":video["avg_frame_rate"],
        "video_codec":video["codec_name"],"audio_codec":audio["codec_name"],
        "duration":float(data["format"]["duration"]),"black_intervals":analysis.count("black_start:"),
        "peak_db":float(peak[1]) if peak else None,"subtitles":any(s["codec_name"]=="mov_text" for s in data["streams"])}
    qc["passed"]=(qc["width"]==1080 and qc["height"]==1920 and qc["fps"]=="24/1"
                   and qc["video_codec"]=="h264" and qc["audio_codec"]=="aac" and qc["subtitles"]
                   and abs(qc["duration"]-duration)<0.12 and qc["black_intervals"]==0
                   and qc["peak_db"] is not None and -60<qc["peak_db"]<0)
    return qc


def compose(doc,store,work):
    simulated=doc.get("provider", "mock-v1")=="mock-v1"
    label="MOCK · " if simulated else ""
    timeline=[]
    selected_candidates=[]
    captions=[]
    position=0
    for i,order in enumerate(doc.get("sequence",[1,2,3,4,5])):
        shot=doc["plan"]["shots"][order-1]
        digest=doc["selected"][order-1]
        clip=next(c for c in doc["candidates"][order-1] if c["sha256"]==digest)
        if not licensed(clip, simulated):
            raise ValueError("Licencia del plano sin verificar.")
        selected_candidates.append(clip)
        (work/f"{i}.mp4").write_bytes(store.read(digest))
        end=position+shot["duration"]
        def stamp(s):
            return f"00:{s//60:02d}:{s%60:02d},000"
        captions.append(f"{i+1}\n{stamp(position)} --> {stamp(end)}\n{label}{shot['caption']}\n")
        timeline.append(dict(order=i+1,shot_order=order,start=position,duration=shot["duration"],sha256=digest))
        position=end
    srt="\n".join(captions).encode()
    (work/"captions.srt").write_bytes(srt)
    (work/"clips.txt").write_text("".join(f"file '{i}.mp4'\n" for i in range(len(timeline))))
    score=doc["plan"].get("decisions",{}).get("disenador_sonoro",{}).get("result",
        {"sample_rate":24000,"frequencies_hz":[220,261.63,329.63,392,261.63]})
    sound(timeline,work/"score.wav",score)
    scale="scale=1080:1920:flags=neighbor" if simulated else "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    encode(["-f","concat","-safe","1","-i","clips.txt","-i","score.wav","-i","captions.srt",
            "-map","0:v","-map","1:a","-map","2:s","-vf",scale,
            "-c:v","libx264","-threads","2","-preset","ultrafast" if simulated else "fast","-crf","20","-c:a","aac",
            "-b:a","96k","-c:s","mov_text","-metadata:s:s:0","language=spa","-movflags","+faststart","reel.mp4"],work)
    encode(["-ss","1","-i","reel.mp4","-frames:v","1","-vf","scale=360:640","-threads","1","cover.png"],work)
    qc=inspect_video(work/"reel.mp4",position)
    if not qc["passed"]:
        raise ValueError("QC técnico fallido: "+json.dumps(qc))
    provenance={"source":"local-ffmpeg-compose", "selected": [c["sha256"] for c in selected_candidates],
                "audio":"original procedural tones", "models":doc.get("home",{}).get("models",[])}
    outputs={key:asset(store,data,mime,simulated=simulated,provenance=provenance) for key,data,mime in (
        ("video",(work/"reel.mp4").read_bytes(),"video/mp4"),("cover",(work/"cover.png").read_bytes(),"image/png"),
        ("subtitles",srt,"application/x-subrip"),("timeline",canonical(timeline),"application/json"),
        ("copy",(label+doc["title"]+"\n"+doc["plan"]["script"]["cta"]).encode(),"text/plain"))}
    version=command(["ffmpeg","-version"],work).stdout.decode().splitlines()[0]
    manifest={"version":1,"simulated":simulated,"license":MEDIA_LICENSE if simulated else REAL_LICENSE,"renderer":RENDERER if simulated else "home-local/1","ffmpeg":version,
              "source":"geometría, alfabeto bitmap y síntesis de tonos del proyecto" if simulated else "Ollama + SDXL + Wan; audio procedural original",
              "native":[135,240] if simulated else [480,832], "upscaled":True,
              "models":doc.get("home",{}).get("models",[]), "human_review":"pending",
              "production_id":doc["id"],"preset":doc["preset"],"character":doc["character"],
              "plan":doc["plan"],"timeline":timeline,"selected_candidates":selected_candidates,
              "renderer_source_sha256":RENDERER_SOURCE_SHA256,
              "home_execution":doc.get("home"),
              "outputs":outputs.copy(),"qc":qc}
    outputs["manifest"]=asset(store,canonical(manifest),"application/json",simulated=simulated,provenance=provenance)
    return {"assets":outputs,"qc":qc,"copy":doc["plan"]["script"]["cta"]}
