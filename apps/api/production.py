import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from packages.contracts.production import BrandPolicy
from .agents import PRESETS, ROLES, preset_data, storyboard
from .media import MEDIA_LICENSE, asset, sprite, input_hash, licensed
from .service import Problem, one
from .storage import canonical

ACTIVE = {"queued","rendering"}
def policy(q,brand):
    row=q("SELECT document FROM brand_policy WHERE brand_id=?",(brand,)).fetchone()
    return json.loads(row["document"]) if row else BrandPolicy().model_dump()



def now():
    return datetime.now(UTC).isoformat()


def conflict(message):
    return Problem(409,"conflict",message)


def summary(doc):
    return {key:doc[key] for key in ("id","campaign_id","brand_id","title","state","revision","simulated")} | {"provider":doc.get("provider","mock-v1")}


def save(query, doc, message):
    doc["revision"] += 1
    query("UPDATE productions SET state=?,revision=?,document=? WHERE id=?",
          (doc["state"],doc["revision"],canonical(doc).decode(),doc["id"]))
    query("INSERT INTO production_events VALUES (?,?,?,?)",(doc["id"],doc["revision"],now(),message))


def invalidate(query, doc):
    if doc["output"]:
        doc["exports"].append(doc["output"])
    doc["output"]={}
    doc["active_review"]=None
    query("UPDATE publications SET status='cancelled' WHERE production_id=? AND status='scheduled'",(doc["id"],))


def load_doc(query,brand,item):
    return json.loads(one(query("SELECT document FROM productions WHERE brand_id=? AND id=?",
                                (brand,item)),"Producción")["document"])


class ProductionService:
    def __init__(self,studio):
        self.studio=studio
        self.db=studio.db
        self.store=studio.blobs

    def new_brand(self, body, key):
        with self.db.transaction(write=True) as q:
            if self.db.pg:
                q("SELECT pg_advisory_xact_lock(8411002)")
            existing=q("SELECT * FROM brands WHERE id=? OR name=? ORDER BY id",(key,body["name"])).fetchall()
            if existing:
                if len(existing)==1 and dict(existing[0])=={"id":key,**body}:
                    return dict(existing[0])
                raise conflict("Nombre o clave de marca ya utilizados.")
            q("INSERT INTO brands VALUES (?,?)",(key,body["name"]))
            return {"id":key,**body}

    def dispatch(self, method, brand, collection, item, action, body, key, resource=None):
        with self.db.transaction(write=method!="GET") as q:
            lock=" FOR UPDATE" if self.db.pg and method!="GET" else ""
            owner=one(q("SELECT * FROM brands WHERE id=?"+lock,(brand,)),"Marca")
            if method=="GET":
                return self.read(q,owner,collection,item,action,resource)
            fingerprint=hashlib.sha256(canonical([collection,item,action,body])).hexdigest()
            prior=q("SELECT fingerprint,response FROM creations WHERE brand_id=? AND request_key=?",
                    (brand,key)).fetchone()
            if prior:
                if prior["fingerprint"]!=fingerprint:
                    raise conflict("La clave identifica otra operación.")
                return json.loads(prior["response"])
            if collection=="policy":
                q("INSERT INTO brand_policy (brand_id,document) VALUES (?,?) ON CONFLICT (brand_id) "
                  "DO UPDATE SET document=excluded.document",(brand,json.dumps(body)))
                result=body
            elif collection=="models":
                record={**body,"id":str(uuid4()),"enabled":False,"status":"pending_local_validation","at":now()}
                if q("SELECT id FROM model_records WHERE brand_id=? AND sha256=?",(brand,body["sha256"])).fetchone():
                    raise conflict("Este hash ya figura en el registro.")
                q("INSERT INTO model_records VALUES (?,?,?,?)",(record["id"],brand,body["sha256"],json.dumps(record)))
                result=record
            elif collection=="characters":
                result=self.character(q,owner,body)
            elif collection=="publications":
                result=self.publish(q,brand,item,action)
            elif item is None:
                result=self.create(q,owner,body)
            else:
                doc=load_doc(q,brand,item)
                result=self.change(q,doc,action,body or {})
            q("INSERT INTO creations VALUES (?,?,?,?)",(brand,key,fingerprint,json.dumps(result)))
            return result

    def character(self,q,owner,body):
        version=q("SELECT MAX(version) AS n FROM characters WHERE brand_id=? AND name=?",
                  (owner["id"],body["name"])).fetchone()["n"] or 0
        char={"id":str(uuid4()),"version":version+1,**body}
        char["reference"]=asset(self.store,sprite(char),"image/png")
        char["views"]={view:asset(self.store,sprite(char,view),"image/png") for view in ("side","back")}
        q("INSERT INTO characters VALUES (?,?,?,?,?)",
          (char["id"],owner["id"],char["name"],char["version"],json.dumps(char)))
        return char

    def create(self,q,owner,body):
        provider=body.get("provider","mock-v1")
        if provider=="home-local-v1":
            if self.db.config.home_root is None:
                raise conflict("HOME est\u00e1 desactivado; use el lanzador dom\u00e9stico con opt-in expl\u00edcito.")
            from .home_runtime import descriptor
            available=descriptor(self.db.config)
            if not available["active"]:
                raise conflict(available["reason"])
        campaign=one(q("SELECT * FROM campaigns WHERE id=? AND brand_id=?",
                       (body["campaign_id"],owner["id"])),"Campaña")
        if body.get("character_id"):
            char=json.loads(one(q("SELECT document FROM characters WHERE id=? AND brand_id=?",
                                  (body["character_id"],owner["id"])),"Personaje")["document"])
        else:
            char={"name":"Lumen","version":1,"color":"#ffe98a","description":"Explorador pixelado de visor oscuro."}
            char["reference"]=asset(self.store,sprite(char),"image/png")
        preset=preset_data(body["preset"])
        plan=storyboard(body["idea"],campaign["name"],owner["name"],preset,char)
        doc={"id":str(uuid4()),"brand_id":owner["id"],"brand_name":owner["name"],"campaign_id":campaign["id"],
             "title":campaign["name"],"simulated":True,"revision":0,"state":"draft","created_at":now(),
             "plan":plan,"plan_history":[],"character":char,"preset":preset,"candidates":[[] for _ in range(5)],
             "selected":[None]*5,"attempts":[0]*5,"output":{},"reviews":[],"exports":[],"error":None}
        doc["provider"]=provider
        if provider=="home-local-v1":
            from .home_runtime import new_state
            doc["home"]=new_state()
        q("INSERT INTO productions VALUES (?,?,?,?,?,?)",(doc["id"],owner["id"],campaign["id"],"draft",0,"{}"))
        save(q,doc,"HOME · producción preparada; pendiente de inferencia" if provider=="home-local-v1" else "Guionista → storyboard → productor · MOCK · contratos v1")
        return summary(doc)

    def read(self,q,owner,collection,item,action,resource):
        brand=owner["id"]
        if collection=="characters":
            if item:
                char=json.loads(one(q("SELECT document FROM characters WHERE brand_id=? AND id=?",(brand,item)),"Personaje")["document"])
                if resource not in {a["sha256"] for a in [char["reference"],*char.get("views",{}).values()]}:
                    raise Problem(404,"missing","Referencia desconocida.")
                return self.store.read(resource),"image/png"
            return [json.loads(r["document"]) for r in q(
                "SELECT document FROM characters WHERE brand_id=? ORDER BY name,version DESC",(brand,))]
        if collection=="policy":
            return policy(q,brand)
        if collection=="registry":
            from .home_runtime import descriptor
            models=[json.loads(r["document"]) for r in q("SELECT document FROM model_records WHERE brand_id=? ORDER BY id",(brand,))]
            return {"presets":[preset_data(k) for k in PRESETS],"roles":ROLES,"models":models,
                    "providers":[{"name":"mock-v1","active":True,"license":MEDIA_LICENSE},
                                 descriptor(self.db.config)]}
        if collection=="publications":
            return [dict(r) for r in q("SELECT * FROM publications WHERE brand_id=? ORDER BY scheduled_at",(brand,))]
        if collection=="metrics":
            rows=q("SELECT status,COUNT(*) AS count FROM publications WHERE brand_id=? GROUP BY status",(brand,))
            return {"source":"local-dry-run","counts":{r["status"]:r["count"] for r in rows},
                    "fixture":{"label":"MOCK · ejemplo de analítica","impressions":120,"plays":75},
                    "external_observations":[]}
        if item is None:
            return [summary(json.loads(r["document"])) for r in q(
                "SELECT document FROM productions WHERE brand_id=? ORDER BY id",(brand,))]
        doc=load_doc(q,brand,item)
        doc.setdefault("active_review",None)
        if action=="assets":
            entries=[doc["character"]["reference"]]+[c for group in doc["candidates"] for c in group]
            entries.extend(m["license_asset"] for m in doc.get("home",{}).get("models",[]) if "license_asset" in m)
            for export in [doc["output"],*doc["exports"]]:
                entries.extend(export.get("assets",{}).values())
            found=next((a for a in entries if a["sha256"]==resource),None)
            if not found:
                raise Problem(404,"missing","Asset no asociado a esta producción.")
            return self.store.read(resource),found["mime"]
        for group,shot in zip(doc["candidates"],doc["plan"]["shots"],strict=True):
            digest=input_hash(doc,shot["order"]-1)
            for candidate in group:
                candidate["selectable"]=candidate["input_hash"]==digest
        doc["activity"]=[dict(r) for r in q(
            "SELECT revision,recorded_at,message FROM production_events WHERE production_id=? ORDER BY revision",(item,))]
        return doc

    def change(self,q,d,action,b):
        is_home=d.get("provider")=="home-local-v1"
        if is_home and action in ("render","regenerate") and self.db.config.home_root is None:
            raise conflict("WORK bloquea inferencia HOME; arranque con el perfil doméstico.")
        if action=="schedule":
            return self.schedule(q,d,b)
        if action=="cancel":
            if d["state"] not in ACTIVE:
                raise conflict("La producción no está en cola.")
            d["state"]="cancelled"
            if is_home and d["home"]["operations"]:
                operation=d["home"]["operations"][-1]
                if operation["kind"]!="script" and operation["state"] in ("submitting","running","uncertain"):
                    operation["cancel_requested"]=True
            message="Cancelación solicitada"
        elif d["state"] in ACTIVE:
            raise conflict("Cancele la ejecución antes de modificar el storyboard.")
        elif action=="render":
            if d["output"]:
                return summary(d)
            if is_home:
                d["home"].update(run_token=str(uuid4()),retry_requested=d["state"] in ("failed","cancelled"))
            d.update(state="queued",error=None)
            message="Montaje en cola"
        elif action=="rewrite":
            if b["revision"]!=d["revision"]:
                raise conflict("El storyboard ha cambiado.")
            if b.get("character_id"):
                d["character"]=json.loads(one(q("SELECT document FROM characters WHERE brand_id=? AND id=?",
                                                (d["brand_id"],b["character_id"])),"Personaje")["document"])
            if b.get("preset"):
                d["preset"]=preset_data(b["preset"])
            d["plan_history"].append(d["plan"])
            d["plan"]=storyboard(b["idea"],d["title"],d["brand_name"],d["preset"],d["character"])
            if is_home:
                from .home_runtime import new_state
                previous=d["home"]
                history=previous.pop("history",[])
                d["home"]=new_state() | {"history":[*history,previous]}
                d["simulated"]=True
            d["attempts"]=[0]*5
            d["selected"]=[None]*5
            invalidate(q,d)
            d["state"]="draft"
            message="HOME · nueva versión pendiente de inferencia" if is_home else "Guion y storyboard versionados · MOCK"
        elif action=="sequence":
            if b["revision"]!=d["revision"]:
                raise conflict("La timeline ha cambiado.")
            if d.get("sequence",[1,2,3,4,5])==b["orders"]:
                return summary(d)
            d["sequence"]=b["orders"]
            invalidate(q,d)
            d["state"]="draft"
            message="Orden del montaje actualizado"
        elif action=="edit":
            if is_home and (not d["home"]["reference_ready"] or b["duration"]!=3):
                raise conflict("HOME requiere guion y referencia generados; el perfil medido usa planos de 3 segundos.")
            if b["revision"]!=d["revision"]:
                raise conflict("El storyboard ha cambiado. Recargue la producción.")
            i=b["order"]-1
            if all(d["plan"]["shots"][i][k]==b[k] for k in ("caption","prompt","duration")):
                return summary(d)
            d["plan_history"].append(json.loads(json.dumps(d["plan"])))
            d["plan"]["shots"][i].update({k:b[k] for k in ("caption","prompt","duration")})
            d["plan"]["script"]["scenes"][i]=b["caption"]
            d["selected"][i]=None
            d["attempts"][i]=0
            invalidate(q,d)
            d["state"]="draft"
            message=f"Storyboard editado · plano {i+1}"
        elif action=="regenerate":
            i=b["order"]-1
            if not d["selected"][i] or d["attempts"][i]>=2:
                raise conflict("Se requiere un candidato y quedan como máximo dos regeneraciones por versión.")
            invalidate(q,d)
            d["selected"][i]=None
            d["attempts"][i]+=1
            if is_home:
                d["home"].update(run_token=str(uuid4()),retry_requested=False)
            d.update(state="queued",error=None)
            message=f"Regeneración selectiva · plano {i+1}"
        elif action=="select":
            i=b["order"]-1
            digest=input_hash(d,i)
            if not any(c["sha256"]==b["sha256"] and c["input_hash"]==digest for c in d["candidates"][i]):
                raise conflict("El candidato no corresponde a esta versión del plano.")
            if d["selected"][i]==b["sha256"]:
                return summary(d)
            invalidate(q,d)
            d["selected"][i]=b["sha256"]
            d["state"]="draft"
            message=f"Candidato seleccionado · plano {i+1}"
        elif action=="review":
            self.current_output(d,b["artifact_hash"])
            if b["verdict"]=="approved" and min(b[k] for k in ("continuity","movement","narrative"))<policy(q,d["brand_id"])["min_score"]:
                raise conflict("Las puntuaciones no alcanzan el umbral de la marca.")
            d["reviews"].append({**b,"at":now()})
            d["active_review"]=d["reviews"][-1]
            if b["verdict"]=="rejected":
                q("UPDATE publications SET status='cancelled' WHERE production_id=? AND status='scheduled'",(d["id"],))
            message="Revisión humana registrada · "+b["verdict"]
        else:
            raise Problem(404,"missing","Operación desconocida.")
        save(q,d,message)
        return summary(d)

    @staticmethod
    def current_output(d,digest):
        out=d["output"]
        if not out or out["assets"]["video"]["sha256"]!=digest or not out["qc"]["passed"]:
            raise conflict("Se requiere el hash actual con QC superado.")
        if any(not licensed(a,d.get("provider","mock-v1")=="mock-v1") for a in out["assets"].values()):
            raise conflict("Licencia sin verificar.")

    def approved(self,q,d,digest):
        self.current_output(d,digest)
        review=d.get("active_review") or {}
        if review.get("artifact_hash")!=digest or review.get("verdict")!="approved":
            raise conflict("Falta aprobación humana del hash actual.")
        if min(review[k] for k in ("continuity","movement","narrative"))<policy(q,d["brand_id"])["min_score"]:
            raise conflict("La revisión no alcanza el umbral actual de la marca.")

    def schedule(self,q,d,b):
        self.approved(q,d,b["artifact_hash"])
        when=datetime.fromisoformat(b["scheduled_at"])
        stamp=when.astimezone(UTC).isoformat()
        local=when.astimezone(ZoneInfo("Europe/Madrid"))
        rules=policy(q,d["brand_id"])
        if rules["paused"] or not rules["start_hour"]<=local.hour<rules["end_hour"]:
            raise conflict("Calendario en pausa u hora fuera de la ventana de la marca.")
        day=local.date().isoformat()
        prior=q("SELECT * FROM publications WHERE production_id=? AND artifact_hash=?",(d["id"],b["artifact_hash"])).fetchone()
        if prior and prior["status"]!="cancelled":
            if prior["scheduled_at"]!=stamp or prior["copy"]!=b["copy"]:
                raise conflict("Ya existe una programación para este hash.")
            return dict(prior)
        n=q("SELECT COUNT(*) AS n FROM publications WHERE brand_id=? AND local_day=? AND status<>'cancelled'",
            (d["brand_id"],day)).fetchone()["n"]
        if n>=rules["daily_limit"]:
            raise conflict("Se alcanzó el límite diario de la marca.")
        row={"id":prior["id"] if prior else str(uuid4()),"production_id":d["id"],"brand_id":d["brand_id"],
             "artifact_hash":b["artifact_hash"],"scheduled_at":stamp,"local_day":day,"status":"scheduled","copy":b["copy"]}
        if prior:
            q("UPDATE publications SET scheduled_at=?,local_day=?,status='scheduled',copy=? WHERE id=?",
              (stamp,day,b["copy"],row["id"]))
        else:
            q("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?)",tuple(row.values()))
        save(q,d,"Programación dry-run guardada")
        return row

    def publish(self,q,brand,item,action):
        row=one(q("SELECT * FROM publications WHERE id=? AND brand_id=?",(item,brand)),"Programación")
        if row["status"]=="dry_run":
            if action=="stop":
                raise conflict("La simulación ya ha terminado.")
            return row
        if action=="stop":
            state="cancelled"
        else:
            if row["status"]!="scheduled" or datetime.fromisoformat(row["scheduled_at"])>datetime.now(UTC):
                raise conflict("La simulación debe estar programada y haber llegado su hora.")
            rules=policy(q,brand)
            local=datetime.fromisoformat(row["scheduled_at"]).astimezone(ZoneInfo("Europe/Madrid"))
            if rules["paused"] or not rules["start_hour"]<=local.hour<rules["end_hour"]:
                raise conflict("La política actual de la marca impide esta simulación.")
            self.approved(q,load_doc(q,brand,row["production_id"]),row["artifact_hash"])
            state="dry_run"
        q("UPDATE publications SET status=? WHERE id=?",(state,item))
        return row | {"status":state}
