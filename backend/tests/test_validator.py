"""Checks on the built-in reference validator itself."""

from copy import deepcopy
from pathlib import Path

import pytest

from scheduler.loader import load_directory
from scheduler.submission import load_submission_directory
from scheduler.validator import validate, validate_files

DATA = Path(__file__).resolve().parents[2] / "01_data"
OUTPUTS = Path(__file__).resolve().parents[2] / "04_solver_outputs"


@pytest.fixture(scope="module")
def instance():
    return load_directory(DATA)


def submission(scenario):
    return load_submission_directory(OUTPUTS / f"scenario_{scenario}")


def rules_fired(report):
    return set(report["detail"]["violations_by_rule"])


@pytest.mark.parametrize("scenario", ["A", "B", "C"])
def test_soft_scores_match_the_solvers_own_accounting(instance, scenario):
    """The validator recomputes scores independently of results.summarize_schedule."""
    import json

    report = validate(instance, submission(scenario))
    solver = json.loads((OUTPUTS / f"scenario_{scenario}" / "report.json").read_text())[
        "solution"
    ]
    scores = report["soft_scores"]
    assert scores["overrun_days_total"] == solver["overrun_days_total"]
    assert scores["eclo_nights_total"] == solver["eclo_nights_total"]
    assert scores["excess_access_nights_total"] == solver["excess_access_nights_total"]
    assert scores["priority_weighted_score"] == pytest.approx(
        solver["priority_weighted_overrun"]
    )
    assert report["detail"]["nights_scheduled"] == solver["nights_scheduled"]


@pytest.mark.parametrize("scenario", ["A", "B", "C"])
def test_published_outputs_break_only_the_known_rules(instance, scenario):
    """Guards the fix: co_share must disappear, and nothing new may appear."""
    strict = validate(instance, submission(scenario), "week")
    loose = validate(instance, submission(scenario), "possession")
    assert rules_fired(strict) <= {"closure", "co_share"}
    assert rules_fired(loose) <= {"co_share"}


def test_scenario_a_rejects_eclo(instance):
    payload = submission("A")
    payload.accesses[0].eclo = 1
    report = validate(instance, payload)
    assert not report["feasible"]
    assert "eclo" in rules_fired(report)


def test_scenario_b_rejects_overrun(instance):
    """B fixes the planned dates, so A's overrunning answer is infeasible under it."""
    payload = submission("A")
    payload.scenario = "B"
    for row in payload.results:
        row.scenario = "B"
    report = validate(instance, payload)
    assert "planned_date" in rules_fired(report)


def test_dropped_activity_is_a_workload_breach(instance):
    payload = submission("C")
    dropped = payload.accesses[0].activity_id
    payload.accesses = [r for r in payload.accesses if r.activity_id != dropped]
    payload.occupancy = [r for r in payload.occupancy if r.activity_id != dropped]
    report = validate(instance, payload)
    assert "workload" in rules_fired(report)
    assert any(dropped in v["detail"] for v in report["hard_violations"])


def test_capacity_allowance_differs_between_scenarios(instance):
    """One possession above supply is fatal in A, inside C's one-night allowance."""
    payload = submission("A")
    busiest = max(
        {(row.location_id, row.week) for row in payload.occupancy},
        key=lambda key: len(
            {
                row.co_share_group
                for row in payload.occupancy
                if (row.location_id, row.week) == key
            }
        ),
    )
    used = len(
        {
            row.co_share_group
            for row in payload.occupancy
            if (row.location_id, row.week) == busiest
        }
    )
    # Squeeze that location's nominal supply so exactly one possession sits above it.
    starved = deepcopy(instance)
    for location in starved.locations:
        if location.location_id == busiest[0]:
            location.supply_capacity = used - 1

    strict = validate(starved, payload)
    assert "capacity" in rules_fired(strict)
    assert busiest[0] in " ".join(v["detail"] for v in strict["hard_violations"])

    payload.scenario = "C"
    for row in payload.results:
        row.scenario = "C"
    assert "capacity" not in rules_fired(validate(starved, payload))


def test_results_must_agree_with_the_schedule(instance):
    payload = submission("A")
    payload.results[0].overrun_days += 5
    report = validate(instance, payload)
    assert "results" in rules_fired(report)


def test_unparseable_submission_reports_format_only(instance):
    report = validate_files(instance, {"RESULTS.csv": b"nonsense\n"})
    assert report["feasible"] is False
    assert report["soft_scores"] == {}
    assert report["hard_violations"][0]["rule"] == "format"
