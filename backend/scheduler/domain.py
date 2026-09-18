"""Scheduling data structures, independent of the API and database."""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Line(Record):
    line_code: str
    line_name: str


class Station(Record):
    station_id: str
    line_code: str
    seq: int = Field(ge=1)
    is_interchange: bool


class Sector(Record):
    sector_id: str
    line_code: str
    from_station_id: str
    to_station_id: str
    seq: int = Field(ge=1)
    is_shared: bool


class Location(Record):
    location_id: str
    location_kind: Literal["tunnel sector", "platform sector"]
    line_code: str
    bound: Literal["EB", "WB"]
    supply_capacity: int = Field(ge=0)


class BufferRule(Record):
    nature_of_works: Literal["Live", "Non-live (Consist)", "Non-live (Others)"]
    up_to_buffer_sectors: int = Field(ge=0)
    opposite_bound_required: bool


class Contract(Record):
    contract_number: str
    contract_description: str
    contract_award_date: date
    activity_type: str
    nature_of_activity: Literal["Live", "Non-live (Consist)", "Non-live (Others)"]
    contract_priority: int = Field(ge=1, le=3)
    contract_completion_date: date
    planned_completion_date: date
    number_of_workfronts: int = Field(ge=1)
    access_type: Literal["PM", "PC", "C"]
    number_of_maximum_access_per_week: int = Field(ge=1)


class Activity(Record):
    activity_id: str
    contract_number: str
    activity_type: str
    start_location_id: str
    end_location_id: str
    total_accesses: int = Field(ge=1)
    planned_start_date: date
    predecessor_activity_id: str = ""
    activity_priority: int = Field(ge=1, le=3)


class Instance(Record):
    lines: list[Line]
    stations: list[Station]
    sectors: list[Sector]
    locations: list[Location]
    buffer_rules: list[BufferRule]
    contracts: list[Contract]
    activities: list[Activity]
    horizon_start: date
    horizon_weeks: int = Field(ge=1, le=260)

    def contract_for(self, activity: Activity) -> Contract:
        return next(
            c
            for c in self.contracts
            if (c.contract_number, c.activity_type)
            == (activity.contract_number, activity.activity_type)
        )

    def week_start(self, week: int) -> date:
        return self.horizon_start + timedelta(weeks=week - 1)

    def week_end(self, week: int) -> date:
        return self.week_start(week) + timedelta(days=6)

    def summary(self) -> dict:
        return {
            "lines": len(self.lines),
            "stations": len(self.stations),
            "locations": len(self.locations),
            "contracts": len({c.contract_number for c in self.contracts}),
            "activities": len(self.activities),
            "total_accesses": sum(a.total_accesses for a in self.activities),
            "horizon_start": self.horizon_start.isoformat(),
            "horizon_weeks": self.horizon_weeks,
        }
