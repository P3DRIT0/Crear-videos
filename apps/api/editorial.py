"""Decisiones acotadas de preproducción. Cada rol usa exclusivamente su entrada local."""
from packages.contracts.production import CreativeDecision

# El nombre de herramienta describe una operación local; ningún rol interpreta comandos.
DESKS = {
    "director_creativo": ("idea, campaña", "enfoque editorial", "leer_brief"),
    "investigador": ("idea", "fuentes aportadas y verificación pendiente", "leer_brief"),
    "estratega_social": ("marca, campaña", "copy y llamada a la acción", "redactar"),
    "planificador": ("formato WORK", "duraciones por plano", "planificar"),
    "director_artistico": ("preset", "paleta y continuidad", "leer_preset"),
    "disenador_personajes": ("personaje versionado", "biblia y referencias", "leer_referencia"),
    "director_fotografia": ("storyboard", "encuadres", "planificar"),
    "animador": ("personaje, plano", "trayectoria de previs", "planificar"),
    "disenador_sonoro": ("duraciones", "partitura sintética", "planificar"),
    "director_voz": ("guion", "pista de voz", "planificar"),
    "editor": ("planos", "especificación de entrega", "planificar"),
    "inspector_visual": ("formato de entrega", "criterios técnicos y rúbrica", "planificar"),
    "publicador": ("política WORK", "destinos y aprobación requerida", "leer_politica"),
    "analista": ("destino", "fuente de observaciones", "leer_politica"),
}


def decisions(idea, title, brand, preset, character, cameras):
    outputs = {
        "director_creativo": {"subject": title, "brief": idea},
        "investigador": {"source": "brief del operador", "external_sources": [], "claims_verified": []},
        "estratega_social": {"caption": f"MOCK · {title}", "cta": "Vuelve a seguir la señal"},
        "planificador": {"seconds": [4,4,4,4,4], "brand": brand},
        "director_artistico": {"background": preset["background"], "accent": preset["accent"],
                               "continuity": preset["continuity"]},
        "disenador_personajes": {"name":character["name"],"version":character["version"],
                                 "reference":character["reference"]["sha256"],"continuity":character["description"]},
        "director_fotografia": {"cameras": list(cameras)},
        "animador": {"method":"trayectoria procedural", "character_shape":character.get("shape","pixel")},
        "disenador_sonoro": {"frequencies_hz":[220,261.63,329.63,392,261.63],"sample_rate":24000},
        "director_voz": {"voice_track":False,"delivery":"subtítulos en castellano"},
        "editor": {"width":1080,"height":1920,"fps":24,"video":"h264","audio":"aac"},
        "inspector_visual": {"technical":["dimensions","duration","fps","blackdetect","peak_db"],
                             "human":["continuity","movement","narrative"]},
        "publicador": {"mode":"dry_run","requires_human_review":True,"real_destination":None},
        "analista": {"source":"local-dry-run","external_metrics":False},
    }
    return {role:CreativeDecision(role=role,prompt_version=role+"/1",tool=DESKS[role][2],
                                  result=result).model_dump() for role,result in outputs.items()}
