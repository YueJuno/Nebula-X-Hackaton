import csv
import io
from pathlib import Path

import pytest

from app.services.scheduling import execute_run
from scheduler.exporter import export_files, zip_files
from scheduler.loader import REQUIRED_FILES, InputError, load_directory, load_files
from scheduler.objectives import delay_coefficient
from scheduler.policies import get_policy
from scheduler.results import Access, Schedule
from scheduler.solver import solve
from scheduler.topology import calculate_footprint
from scheduler.validator import validate_submission

PUBLIC = Path(__file__).resolve().parents[2] / "01_data"


@pytest.fixture
def public_instance():
    return load_directory(PUBLIC)


def test_load_public_instance(public_instance):
    assert len(public_instance.activities) == 54
    assert public_instance.summary()["contracts"] == 14
    assert public_instance.summary()["locations"] == 76
    assert public_instance.week_end(1).isoformat() == "2027-01-10"


def test_missing_file_and_unknown_contract():
    files = {name: (PUBLIC / name).read_bytes() for name in REQUIRED_FILES}
    with pytest.raises(InputError, match="Missing"):
        load_files(
            {key: value for key, value in files.items() if key != "01_LINES.csv"}
        )
    files["08_ACTIVITY_DETAILS.csv"] = files["08_ACTIVITY_DETAILS.csv"].replace(
        b"A001,C001,", b"A001,NOPE,"
    )
    with pytest.raises(InputError, match="unknown contract"):
        load_files(files)


def test_duplicate_headers_are_rejected():
    files = {name: (PUBLIC / name).read_bytes() for name in REQUIRED_FILES}
    files["01_LINES.csv"] = b"line_code,line_code\nALP,Alpha\n"
    with pytest.raises(InputError, match="duplicate column"):
        load_files(files)


def test_interchange_live_footprint_and_nonlive_isolation(public_instance):
    activity = public_instance.activities[0].model_copy(
        update={
            "start_location_id": "SEC:ALP:H01_H02:EB",
            "end_location_id": "SEC:ALP:H01_H02:EB",
        }
    )
    contract = public_instance.contract_for(activity)
    nonlive = calculate_footprint(public_instance, activity)
    assert not nonlive.mirrored and not nonlive.cross_line
    assert "PLAT:ALP:H01:EB" in nonlive.occupied
    instance = public_instance.model_copy(
        update={
            "contracts": [
                c.model_copy(update={"nature_of_activity": "Live"})
                if c == contract
                else c
                for c in public_instance.contracts
            ]
        }
    )
    live = calculate_footprint(instance, activity)
    assert "SEC:ALP:H01_H02:WB" in live.mirrored
    assert "SEC:BET:H01_H02:WB" in live.cross_line
    assert live.affected_lines == ["ALP", "BET"]


def test_solver_is_gated_before_search(public_instance, monkeypatch):
    from ortools.sat.python import cp_model

    def forbidden_search(*args, **kwargs):
        pytest.fail("Solver search must not run without constraints")

    monkeypatch.setattr(cp_model.CpSolver, "solve", forbidden_search)
    with pytest.raises(NotImplementedError, match="Missing railway constraints"):
        solve(public_instance, "A")


def test_preparation_never_claims_feasibility(public_instance):
    result = execute_run(public_instance.model_dump(mode="json"), {}, "C")
    assert result["status"] == "blocked"
    assert result["schedule"] is None and result["submission_zip"] is None
    assert len(result["report"]["footprints"]) == 54
    assert len(result["report"]["missing_constraints"]) == 5


def test_policy_and_priority_bands():
    assert not get_policy("A").allow_eclo
    assert get_policy("B").fixed_deadlines
    assert get_policy("C").max_excess_per_location_week == 1
    assert delay_coefficient(1, 3) > delay_coefficient(2, 1)
    assert delay_coefficient(2, 3) > delay_coefficient(3, 1)


def test_export_shapes_dates_and_archive(public_instance):
    from zipfile import ZipFile

    activity = public_instance.activities[0]
    instance = public_instance.model_copy(
        update={
            "activities": [activity],
            "contracts": [public_instance.contract_for(activity)],
        }
    )
    schedule = Schedule(
        accesses=[
            Access(
                activity_id=activity.activity_id,
                week=30,
                eclo=0,
                access_night=1,
                groups={activity.start_location_id: "p1"},
            )
        ],
        objective_score=0,
        solver_status="TEST",
    )
    files = export_files(instance, schedule, "A")
    rows = list(csv.DictReader(io.StringIO(files["RESULTS.csv"].decode())))
    assert rows[0]["scenario"] == "A"
    assert rows[0]["simulated_completion_date"] == instance.week_end(30).isoformat()
    with ZipFile(io.BytesIO(zip_files(files))) as archive:
        assert set(archive.namelist()) == {
            "SCHEDULE_ACCESS.csv",
            "SCHEDULE_OCCUPANCY.csv",
            "RESULTS.csv",
        }


def test_validator_missing_is_not_feasible(tmp_path):
    report = validate_submission(None, tmp_path, tmp_path)
    assert report["status"] == "unavailable" and report["feasible"] is None
