"""Parse the three submission CSVs. Structure only; railway rules live in rules.py."""

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scheduler.loader import InputError, read_rows


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccessRow(Row):
    activity_id: str
    access_seq: int = Field(ge=1)
    week: int = Field(ge=1)
    eclo: int = Field(ge=0, le=1)
    access_night: int = Field(ge=1)


class OccupancyRow(Row):
    activity_id: str
    week: int = Field(ge=1)
    location_id: str
    co_share_group: str = Field(min_length=1)


class ResultRow(Row):
    scenario: Literal["A", "B", "C"]
    contract_number: str
    simulated_completion_date: date
    overrun_days: int = Field(ge=0)


class Submission(BaseModel):
    scenario: Literal["A", "B", "C"]
    accesses: list[AccessRow]
    occupancy: list[OccupancyRow]
    results: list[ResultRow]


SUBMISSION_FILES = ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv")
TABLES = {
    "SCHEDULE_ACCESS.csv": ("accesses", AccessRow),
    "SCHEDULE_OCCUPANCY.csv": ("occupancy", OccupancyRow),
    "RESULTS.csv": ("results", ResultRow),
}


def load_submission_files(files: dict[str, bytes]) -> Submission:
    missing = set(SUBMISSION_FILES) - set(files)
    if missing:
        raise InputError([f"Missing submission files: {', '.join(sorted(missing))}"])
    data: dict = {}
    errors: list[str] = []
    for filename, (key, row_type) in TABLES.items():
        rows = read_rows(filename, files[filename], set(row_type.model_fields))
        records = []
        for number, row in enumerate(rows, 2):
            try:
                records.append(row_type.model_validate(row))
            except ValidationError as exc:
                errors.extend(
                    f"{filename}, row {number}, {'.'.join(map(str, e['loc']))}: {e['msg']}"
                    for e in exc.errors()
                )
        data[key] = records
    if errors:
        raise InputError(errors)
    # The validator scores one policy at a time, so a mixed RESULTS.csv is unscoreable.
    scenarios = sorted({row.scenario for row in data["results"]})
    if len(scenarios) != 1:
        raise InputError(
            [f"RESULTS.csv: expected exactly one scenario, found {', '.join(scenarios)}"]
        )
    duplicates = [row.contract_number for row in data["results"]]
    if len(duplicates) != len(set(duplicates)):
        raise InputError(["RESULTS.csv: duplicate contract_number rows"])
    return Submission(scenario=scenarios[0], **data)


def load_submission_directory(directory: Path) -> Submission:
    try:
        return load_submission_files(
            {name: (directory / name).read_bytes() for name in SUBMISSION_FILES}
        )
    except OSError as exc:
        raise InputError([f"Cannot read submission files: {exc.filename}"]) from exc
