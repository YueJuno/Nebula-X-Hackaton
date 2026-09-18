from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    summary: dict
    created_at: datetime


class RunRequest(BaseModel):
    dataset_id: str = Field(min_length=36, max_length=36)
    scenario: Literal["A", "B", "C"]
    # Section 2.4 rule 3 is ambiguous; "week" is the reading that satisfies both.
    buffer_granularity: Literal["week", "possession"] = "week"


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_id: str
    scenario: str
    buffer_granularity: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    message: str | None
    report: dict | None
    schedule: dict | None
