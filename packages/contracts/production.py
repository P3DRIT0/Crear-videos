from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import model_validator, field_validator, AwareDatetime, Field, StringConstraints

from .models import Model, Name, Objective

Hash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Index = Annotated[int, Field(ge=1, le=5)]
Duration = Annotated[int, Field(ge=3, le=5)]
Score = Annotated[int, Field(ge=1, le=5)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Preset = Literal["motion", "cinematic", "anime", "cartoon", "clay", "miniature", "product"]


class BrandInput(Model):
    name: Name


class CharacterInput(Model):
    name: Name
    description: Objective
    color: Color
    shape: Literal["pixel","cursor","orb"] = "pixel"


class ProductionInput(Model):
    campaign_id: UUID
    idea: Objective
    preset: Preset = "motion"
    character_id: UUID | None = None


class Shot(Model):
    order: Index
    duration: Duration
    caption: Name
    camera: Name
    prompt: Objective
    seed: int = Field(ge=0, le=2**32-1)


class Script(Model):
    version: Literal[1] = 1
    hook: Name
    scenes: list[Name] = Field(min_length=5, max_length=5)
    cta: Name


class CreativeDecision(Model):
    role: Name
    prompt_version: Name
    tool: Name
    result: dict


class Plan(Model):
    simulated: Literal[True] = True
    provider: Literal["mock-v1"] = "mock-v1"
    idea: Objective
    script: Script
    shots: list[Shot] = Field(min_length=5, max_length=5)
    trace: list[dict] = Field(default_factory=list)
    decisions: dict[str, CreativeDecision] = Field(default_factory=dict)


class ShotEdit(Model):
    order: Index
    caption: Name
    prompt: Objective
    duration: Duration
    revision: int = Field(ge=1)


class ShotChoice(Model):
    order: Index
    sha256: Hash


class ShotRetry(Model):
    order: Index


class ReviewInput(Model):
    artifact_hash: Hash
    reviewer: Name
    verdict: Literal["approved","rejected"]
    continuity: Score
    movement: Score
    narrative: Score
    notes: Objective


class ScheduleInput(Model):
    artifact_hash: Hash
    scheduled_at: AwareDatetime
    caption: Objective = Field(alias="copy")
    mode: Literal["dry_run"] = "dry_run"


class ProductionSummary(Model):
    id: UUID
    campaign_id: UUID
    brand_id: UUID
    title: str
    state: str
    revision: int
    simulated: Literal[True]


class SequenceEdit(Model):
    orders: list[Index] = Field(min_length=5, max_length=5)
    revision: int = Field(ge=1)

    @field_validator("orders")
    @classmethod
    def permutation(cls, values):
        if sorted(values)!=[1,2,3,4,5]:
            raise ValueError("Cada plano debe aparecer una vez.")
        return values


class ProductionDetail(ProductionSummary):
    brand_name: str
    active_review: dict | None = None
    sequence: list[Index] = Field(default_factory=lambda:[1,2,3,4,5])
    plan: Plan
    preset: dict
    character: dict
    candidates: list[list[dict]]
    selected: list[str | None]
    attempts: list[int]
    plan_history: list[Plan]
    output: dict
    reviews: list[dict]
    activity: list[dict]
    error: str | None
    created_at: datetime
    exports: list[dict]


class ModelRecordInput(Model):
    name: Name
    version: Name
    source_url: Annotated[str, StringConstraints(pattern=r"^https://[^\s@]+$", max_length=500)]
    sha256: Hash
    license_id: Name
    restrictions: Objective
    checked_by: Name

class BrandPolicy(Model):
    daily_limit: int = Field(default=3, ge=1, le=20)
    start_hour: int = Field(default=0, ge=0, le=23)
    end_hour: int = Field(default=24, ge=1, le=24)
    min_score: Score = 3
    paused: bool = False

    @model_validator(mode="after")
    def valid_window(self):
        if self.start_hour>=self.end_hour:
            raise ValueError("La hora de fin debe ser posterior al inicio.")
        return self


class RewriteInput(Model):
    idea: Objective
    character_id: UUID | None = None
    preset: Preset | None = None
    revision: int = Field(ge=1)
