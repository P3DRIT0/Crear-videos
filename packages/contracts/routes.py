"""Una tabla para el enrutador HTTP y la descripción del contrato."""
from dataclasses import dataclass
from pydantic import TypeAdapter

from .models import (Brand, Brief, Campaign, CampaignEdit, CampaignInput, Capabilities, Error, Health,
                     Job, JobEdit, JobInput)

PREFIX = "/api/v1"


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    output: object
    body: object = None
    status: int = 200
    key: bool = False


ROUTES = [
    Route("GET", "/health", Health),
    Route("GET", "/system/capabilities", Capabilities),
    Route("GET", "/brands", list[Brand]),
]
for collection, model, create, edit in [("campaigns", Campaign, CampaignInput, CampaignEdit),
                                       ("jobs", Job, JobInput, JobEdit)]:
    path = "/brands/{brand}/" + collection
    item = path + "/{item}"
    ROUTES.extend([
        Route("GET", path, list[model]),
        Route("POST", path, model, create, 201, True),
        Route("GET", item, model),
        Route("PATCH", item, model, edit),
        Route("DELETE", item, None, status=204),
    ])
ROUTES.extend([
    Route("POST", "/brands/{brand}/jobs/{item}/run", Job),
    Route("GET", "/brands/{brand}/jobs/{item}/artifact", Brief),
])


from .production import (RewriteInput, BrandPolicy, SequenceEdit, ModelRecordInput, BrandInput, CharacterInput, ProductionInput, ProductionSummary,
                         ProductionDetail, ReviewInput, ScheduleInput, ShotChoice, ShotEdit, ShotRetry)

BRAND_PATH = "/brands/{brand}/"
PROD_PATH = BRAND_PATH + "productions"
ITEM = PROD_PATH + "/{item}"
ROUTES.extend([
    Route("POST", "/brands", Brand, BrandInput, 201, True),
    Route("GET", BRAND_PATH+"registry", dict),
    Route("POST", BRAND_PATH+"models", dict, ModelRecordInput, 201, True),
    Route("GET", BRAND_PATH+"characters", list[dict]),
    Route("GET", BRAND_PATH+"characters/{item}/assets/{digest}", bytes),
    Route("POST", BRAND_PATH+"characters", dict, CharacterInput, 201, True),
    Route("GET", PROD_PATH, list[ProductionSummary]),
    Route("POST", PROD_PATH, ProductionSummary, ProductionInput, 201, True),
    Route("GET", ITEM, ProductionDetail),
    Route("GET", ITEM+"/assets/{digest}", bytes),
    Route("GET", ITEM+"/events", str),
    Route("GET", BRAND_PATH+"policy", BrandPolicy),
    Route("POST", BRAND_PATH+"policy", BrandPolicy, BrandPolicy, key=True),
    Route("GET", BRAND_PATH+"metrics", dict),
    Route("GET", BRAND_PATH+"publications", list[dict]),
])
for operation, model in [("rewrite",RewriteInput),("sequence",SequenceEdit),("edit",ShotEdit),("regenerate",ShotRetry),("select",ShotChoice),
                         ("render",None),("cancel",None),("review",ReviewInput),("schedule",ScheduleInput)]:
    ROUTES.append(Route("POST", ITEM+"/"+operation, dict if operation=="schedule" else ProductionSummary,
                        model, key=True))
for operation in ("simulate","stop"):
    ROUTES.append(Route("POST", BRAND_PATH+"publications/{item}/"+operation,dict,key=True))

def openapi():
    schemas = {}

    def content(model):
        schema = TypeAdapter(model).json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        return {"application/json": {"schema": schema}}

    paths = {}
    for route in ROUTES:
        params = [{"name": name, "in": "path", "required": True,
                   "schema": {"type": "string", "format": "uuid"}}
                  for name in ("brand", "item") if "{" + name + "}" in route.path]
        if "{digest}" in route.path:
            params.append({"name":"digest","in":"path","required":True,"schema":{"type":"string","pattern":"^[0-9a-f]{64}$"}})
        if route.key:
            params.append({"name": "Idempotency-Key", "in": "header", "required": True,
                           "schema": {"type": "string", "format": "uuid"}})
        success = {"description": "Operación completada"}
        if route.output is bytes:
            success["content"] = {"*/*": {"schema":{"type":"string","format":"binary"}}}
        elif route.path.endswith("/events"):
            success["content"] = {"text/event-stream": {"schema":{"type":"string"}}}
        elif route.output:
            success["content"] = content(route.output)
        operation = {"parameters": params, "responses": {str(route.status): success,
                     "default": {"description": "Error", "content": content(Error)}}}
        if route.body:
            operation["requestBody"] = {"required": True, "content": content(route.body)}
        paths.setdefault(PREFIX + route.path, {})[route.method.lower()] = operation
    return {"openapi": "3.1.0", "info": {"title": "AI Creative Studio", "version": "0.3.0"},
            "paths": paths, "components": {"schemas": schemas}}
