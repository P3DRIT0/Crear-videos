"""Agentes WORK sin E/S. Cada rol produce solo datos acotados por su contrato."""
import hashlib
import time

from packages.contracts.production import Plan, Script, Shot
from .storage import canonical
from .editorial import DESKS, decisions

PRESETS = {
    "motion": ("Motion graphics", "1b1634", "f1ae56", "rejilla y desplazamientos lineales"),
    "cinematic": ("Cinematic 3D", "182336", "fcb675", "contraluz y profundidad"),
    "anime": ("Anime", "27264e", "ff99ad", "siluetas y barridos diagonales"),
    "cartoon": ("Cartoon 2D", "234343", "ffe276", "formas planas y movimiento elástico"),
    "clay": ("Clay / stop motion", "352827", "ffb597", "pasos cortos y textura mate"),
    "miniature": ("Miniature world", "243c33", "badc83", "encuadre elevado y escala constante"),
    "product": ("Product CGI", "1f2b34", "b8dbf0", "producto centrado y luz lateral"),
}
ROLES = {
    "guionista": {"input":"idea, campaña", "output":"Script", "version":"guion/2", "steps":1},
    "storyboard": {"input":"Script, preset, personaje", "output":"Shot[5]", "version":"planos/2", "steps":5},
    "productor": {"input":"Script, Shot[5]", "output":"Plan", "version":"productor/1", "steps":1},
}
for role,(inputs,output,tool) in DESKS.items():
    ROLES[role]={"input":inputs,"output":output,"version":role+"/1","steps":1,"tools":[tool]}
for spec in ROLES.values():
    spec.setdefault("tools",["validar_json"])
    spec.update(timeout_seconds=2, fallback="error_local", provider="mock-v1")
CAMERAS = ("General fijo", "Acercamiento", "Travelling lateral", "Primer plano", "Retorno al encuadre inicial")


def preset_data(key):
    name, background, accent, rule = PRESETS[key]
    return dict(id=key, name=name, background=background, accent=accent,
                continuity=rule, version=1, provider="mock-v1")


def storyboard(idea, title, brand, preset, character, timeout=2):
    deadline = time.monotonic() + timeout
    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("El productor agotó el presupuesto de tiempo.")
    def record(role, inputs, outputs, steps):
        check()
        spec=ROLES[role]
        if steps>spec["steps"]:
            raise ValueError("Presupuesto de pasos agotado.")
        trace.append({"role":role,"prompt_version":spec["version"],"steps":steps,"simulated":True,
                      "input_sha256":hashlib.sha256(canonical(inputs)).hexdigest(),
                      "output_sha256":hashlib.sha256(canonical(outputs)).hexdigest()})
    trace=[]
    check()
    desk=decisions(idea,title,brand,preset,character,CAMERAS)
    for role,decision in desk.items():
        record(role,[idea,title,preset["id"],character["version"]],decision,1)
    lead = character["name"][:45]
    subject = title.split(" · ")[-1][:55]
    hook = f"Una señal en {subject}"
    if "cursor" in idea.lower() and "luz" in idea.lower():
        scenes=["Un píxel se enciende", "El cursor descubre el destello", "La señal cruza la cuadrícula",
                f"La luz revela {brand[:60]}", "El píxel regresa al origen"]
    else:
        first=idea.strip().split(".")[0][:85].strip() or subject
        scenes=[first, f"{lead} descubre la señal", "La luz recorre la cuadrícula",
                f"Aparece {brand[:60]}", "Volvemos al primer destello"]
    script = Script(hook=hook, scenes=scenes, cta=desk["estratega_social"]["result"]["cta"])
    record("guionista",[idea,title,brand],script.model_dump(),1)
    shots = []
    for index, caption in enumerate(scenes):
        check()
        material=canonical([idea,preset,character,index])
        seed=int.from_bytes(hashlib.sha256(material).digest()[:4],"big")
        prompt=f"{caption}. {CAMERAS[index]}. {preset['continuity']}. Idea: {idea}"
        shots.append(Shot(order=index+1,duration=desk["planificador"]["result"]["seconds"][index],caption=caption,camera=CAMERAS[index],
                          prompt=prompt[:1000],seed=seed))
    scene_data=[s.model_dump() for s in shots]
    record("storyboard",[script.model_dump(),preset,character],scene_data,len(shots))
    plan=Plan(idea=idea,script=script,shots=shots,decisions=desk)
    record("productor",scene_data,plan.model_dump(exclude={"trace"}),1)
    plan.trace=trace
    return plan.model_dump(mode="json")
