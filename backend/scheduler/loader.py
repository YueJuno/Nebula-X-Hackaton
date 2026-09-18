"""CSV parsing and input integrity checks (not railway scheduling constraints)."""

import csv
import io
from pathlib import Path

from pydantic import ValidationError

from scheduler.domain import (
    Activity,
    BufferRule,
    Contract,
    Instance,
    Line,
    Location,
    Sector,
    Station,
)

TABLES = {
    "01_LINES.csv": ("lines", Line),
    "02_STATIONS.csv": ("stations", Station),
    "03_SECTORS.csv": ("sectors", Sector),
    "04_LOCATION_SUPPLY.csv": ("locations", Location),
    "05_BUFFER_LOCATION.csv": ("buffer_rules", BufferRule),
    "07_PROJECT_DETAILS.csv": ("contracts", Contract),
    "08_ACTIVITY_DETAILS.csv": ("activities", Activity),
}
REQUIRED_FILES = (
    "01_LINES.csv",
    "02_STATIONS.csv",
    "03_SECTORS.csv",
    "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv",
    "06_PARAMETERS.csv",
    "07_PROJECT_DETAILS.csv",
    "08_ACTIVITY_DETAILS.csv",
)


class InputError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors[:20]))


def read_rows(name: str, content: bytes, columns: set[str]) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise InputError([f"{name}: duplicate column names"])
        if set(headers) != columns:
            raise InputError([f"{name}: expected columns {', '.join(sorted(columns))}"])
        rows = []
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise InputError([f"{name}, row {number}: incorrect number of fields"])
            rows.append({key: value.strip() for key, value in row.items()})
        if not rows:
            raise InputError([f"{name}: no data rows"])
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise InputError([f"{name}: invalid UTF-8 CSV"]) from exc


def load_files(files: dict[str, bytes]) -> Instance:
    missing = set(REQUIRED_FILES) - set(files)
    unexpected = set(files) - set(REQUIRED_FILES)
    if missing or unexpected:
        raise InputError(
            [
                f"Missing: {', '.join(sorted(missing)) or 'none'}; unexpected: {', '.join(sorted(unexpected)) or 'none'}"
            ]
        )
    data = {}
    errors = []
    for filename, (key, record_type) in TABLES.items():
        rows = read_rows(filename, files[filename], set(record_type.model_fields))
        records = []
        for number, row in enumerate(rows, 2):
            try:
                records.append(record_type.model_validate(row))
            except ValidationError as exc:
                errors.extend(
                    f"{filename}, row {number}, {'.'.join(map(str, e['loc']))}: {e['msg']}"
                    for e in exc.errors()
                )
        data[key] = records
    parameters = read_rows(
        "06_PARAMETERS.csv", files["06_PARAMETERS.csv"], {"key", "value"}
    )
    values = {row["key"]: row["value"] for row in parameters}
    if len(values) != len(parameters) or set(values) != {
        "horizon_start",
        "horizon_weeks",
    }:
        errors.append(
            "06_PARAMETERS.csv: expected unique horizon_start and horizon_weeks keys"
        )
    if errors:
        raise InputError(errors)
    try:
        instance = Instance(**data, **values)
    except ValidationError as exc:
        raise InputError([f"Parameters: {e['msg']}" for e in exc.errors()]) from exc
    check_references(instance)
    return instance


def check_references(instance: Instance) -> None:
    errors = []

    def unique(values, label):
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {label}")

    unique([x.line_code for x in instance.lines], "line codes")
    unique([(x.line_code, x.station_id) for x in instance.stations], "line/station IDs")
    unique([(x.line_code, x.seq) for x in instance.stations], "station sequences")
    unique([x.sector_id for x in instance.sectors], "sector IDs")
    unique([x.location_id for x in instance.locations], "location IDs")
    unique(
        [(x.contract_number, x.activity_type) for x in instance.contracts],
        "contract/type pairs",
    )
    unique([x.activity_id for x in instance.activities], "activity IDs")
    unique([x.nature_of_works for x in instance.buffer_rules], "buffer rules")
    lines = {x.line_code for x in instance.lines}
    stations = {(x.line_code, x.station_id): x for x in instance.stations}
    sectors = {x.sector_id: x for x in instance.sectors}
    locations = {x.location_id: x for x in instance.locations}
    contracts = {(x.contract_number, x.activity_type): x for x in instance.contracts}
    activities = {x.activity_id: x for x in instance.activities}
    for station in instance.stations:
        if station.line_code not in lines:
            errors.append(f"Station {station.station_id}: unknown line")
    for sector in instance.sectors:
        start = stations.get((sector.line_code, sector.from_station_id))
        end = stations.get((sector.line_code, sector.to_station_id))
        if not start or not end or end.seq != start.seq + 1:
            errors.append(
                f"Sector {sector.sector_id}: expected adjacent stations on its line"
            )
        if (
            sector.sector_id
            != f"SEC:{sector.line_code}:{sector.from_station_id}_{sector.to_station_id}"
        ):
            errors.append(f"Sector {sector.sector_id}: inconsistent sector ID")
    for location in instance.locations:
        parts = location.location_id.split(":")
        valid = (
            len(parts) == 4
            and parts[1] == location.line_code
            and parts[3] == location.bound
        )
        if location.location_kind == "tunnel sector":
            valid = valid and parts[0] == "SEC" and ":".join(parts[:3]) in sectors
        else:
            valid = (
                valid
                and parts[0] == "PLAT"
                and (location.line_code, parts[2]) in stations
            )
        if not valid:
            errors.append(
                f"Location {location.location_id}: invalid location reference"
            )
    for contract in instance.contracts:
        if contract.nature_of_activity not in {
            x.nature_of_works for x in instance.buffer_rules
        }:
            errors.append(f"Contract {contract.contract_number}: missing buffer rule")
    for activity in instance.activities:
        if (activity.contract_number, activity.activity_type) not in contracts:
            errors.append(f"Activity {activity.activity_id}: unknown contract/type")
        start, end = (
            locations.get(activity.start_location_id),
            locations.get(activity.end_location_id),
        )
        if (
            not start
            or not end
            or (start.line_code, start.bound) != (end.line_code, end.bound)
        ):
            errors.append(
                f"Activity {activity.activity_id}: endpoints must exist on the same line/bound"
            )
        predecessor = activity.predecessor_activity_id
        if predecessor and (
            predecessor not in activities or predecessor == activity.activity_id
        ):
            errors.append(f"Activity {activity.activity_id}: invalid predecessor")
    for activity in instance.activities:
        seen = set()
        current = activity
        while current.predecessor_activity_id in activities:
            if current.activity_id in seen:
                errors.append(f"Activity {activity.activity_id}: predecessor cycle")
                break
            seen.add(current.activity_id)
            current = activities[current.predecessor_activity_id]
    # Topology requires both bounds and every station/sector to have capacity records.
    for bound in ("EB", "WB"):
        expected = {
            f"PLAT:{s.line_code}:{s.station_id}:{bound}" for s in instance.stations
        }
        expected |= {f"{s.sector_id}:{bound}" for s in instance.sectors}
        if missing := expected - set(locations):
            errors.append(f"Missing location supply: {', '.join(sorted(missing))}")
    if errors:
        raise InputError(errors)


def load_directory(directory: Path) -> Instance:
    try:
        return load_files(
            {name: (directory / name).read_bytes() for name in REQUIRED_FILES}
        )
    except OSError as exc:
        raise InputError([f"Cannot read input files: {exc.filename}"]) from exc
