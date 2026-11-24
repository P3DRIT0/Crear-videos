"""Modelos que comparten la validación de la API y el documento OpenAPI."""
from typing import Annotated, Literal
from uuid import UUID
from datetime import datetime

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, with_config
from typing_extensions import TypedDict


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100,
                                        pattern=r"^[^\x00-\x1f\x7f]+$")]
Objective = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000,
                                             pattern=r"^[^\x00]+$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampaignInput(Model):
    name: Name
    objective: Objective


@with_config(ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1}))
class CampaignChanges(TypedDict, total=False):
    name: Name
    objective: Objective


def require_changes(value: CampaignChanges) -> CampaignChanges:
    if not value:
        raise ValueError("Indique al menos un campo.")
    return value


CampaignEdit = Annotated[CampaignChanges, AfterValidator(require_changes)]


class Campaign(CampaignInput):
    id: UUID
    brand_id: UUID
    created_at: datetime


class JobInput(Model):
    campaign_id: UUID
    label: Name


class JobEdit(Model):
    label: Name


class Job(JobInput):
    id: UUID
    brand_id: UUID
    state: Literal["pending", "succeeded", "failed"]
    sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None
    error: str | None
    created_at: datetime


class Brand(Model):
    id: UUID
    name: str


class Brief(Model):
    version: Literal[1]
    brand: Brand
    campaign: Campaign


class Health(Model):
    status: Literal["ok"]
    database: str
    schema_version: int
    storage: Literal["ok"]


class Capabilities(Model):
    profile: Literal["work", "home16"]
    database: str
    gpu_jobs: Literal[0, 1]
    remote_inference: Literal[False]
    publishing: Literal[False]
    executor: Literal["manual-sync"]
    home_enabled: bool = False
    offline_policy_installed: bool = False


class Error(Model):
    code: str
    message: str
