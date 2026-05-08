from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_url: HttpUrl


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: HttpUrl | None = None


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    trigger: Literal["manual", "scheduled", "api"] = "manual"
    max_pages: int | None = Field(default=None, ge=1, le=10000)
    region: str | None = Field(default=None, max_length=40)
    consent_state: Literal["accept", "reject", "no_selection", "gpc_reject"] | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    status: str
    trigger: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    pages_done: int
    pages_total_estimate: int | None
    config: dict[str, Any]
    error_code: str | None
    error_message: str | None

