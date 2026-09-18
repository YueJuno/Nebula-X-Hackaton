import csv
import io
from zipfile import ZIP_DEFLATED, ZipFile

from scheduler.domain import Instance
from scheduler.results import Schedule


def csv_bytes(columns, rows) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def export_files(
    instance: Instance, schedule: Schedule, scenario: str
) -> dict[str, bytes]:
    if scenario not in {"A", "B", "C"}:
        raise ValueError("Unknown scenario")
    activities = {a.activity_id: a for a in instance.activities}
    grouped = {key: [] for key in activities}
    for access in schedule.accesses:
        if access.activity_id not in grouped:
            raise ValueError("Schedule contains an unknown activity")
        grouped[access.activity_id].append(access)
    if any(not accesses for accesses in grouped.values()):
        raise ValueError("Cannot export a submission with omitted activities")
    access_rows, occupancy_rows = [], []
    contract_weeks = {}
    for activity_id, accesses in sorted(grouped.items()):
        for sequence, access in enumerate(
            sorted(accesses, key=lambda x: (x.week, x.access_night)), 1
        ):
            access_rows.append(
                {
                    "activity_id": activity_id,
                    "access_seq": sequence,
                    "week": access.week,
                    "eclo": access.eclo,
                    "access_night": access.access_night,
                }
            )
            occupancy_rows.extend(
                {
                    "activity_id": activity_id,
                    "week": access.week,
                    "location_id": location,
                    "co_share_group": group,
                }
                for location, group in sorted(access.groups.items())
            )
            contract = activities[activity_id].contract_number
            contract_weeks[contract] = max(contract_weeks.get(contract, 0), access.week)
    result_rows = []
    for number in sorted({c.contract_number for c in instance.contracts}):
        if number not in contract_weeks:
            raise ValueError(f"Contract {number} has no scheduled activities")
        completed = instance.week_end(contract_weeks[number])
        deadline = min(
            c.planned_completion_date
            for c in instance.contracts
            if c.contract_number == number
        )
        result_rows.append(
            {
                "scenario": scenario,
                "contract_number": number,
                "simulated_completion_date": completed.isoformat(),
                "overrun_days": max(0, (completed - deadline).days),
            }
        )
    return {
        "SCHEDULE_ACCESS.csv": csv_bytes(
            ["activity_id", "access_seq", "week", "eclo", "access_night"], access_rows
        ),
        "SCHEDULE_OCCUPANCY.csv": csv_bytes(
            ["activity_id", "week", "location_id", "co_share_group"], occupancy_rows
        ),
        "RESULTS.csv": csv_bytes(
            [
                "scenario",
                "contract_number",
                "simulated_completion_date",
                "overrun_days",
            ],
            result_rows,
        ),
    }


def zip_files(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()
