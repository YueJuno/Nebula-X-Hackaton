"""Why-late attribution and the counterfactual lever sweep."""

from pathlib import Path

import pytest

from scheduler.explain import (
    Lever,
    apply_lever,
    candidate_levers,
    cheapest_unlocks,
    explain_delays,
    measure,
)
from scheduler.loader import load_directory
from scheduler.solver import solve

PUBLIC = Path(__file__).resolve().parents[2] / "01_data"


@pytest.fixture(scope="module")
def instance():
    return load_directory(PUBLIC)


@pytest.fixture(scope="module")
def schedule_a(instance):
    return solve(instance, "A", 60)


def test_window_shortfall_is_detected_and_dominates(instance, schedule_a):
    """A036 needs 7 nights inside a 5-week window; one night a week cannot fit."""
    rows = {row["activity_id"]: row for row in explain_delays(instance, schedule_a)}
    # Which activities contend depends on the buffer reading, but the two with a
    # structural shortfall overrun under any of them.
    assert {"A036", "A059"} <= set(rows)
    assert all(
        row["primary_factor"] == "window"
        for row in rows.values()
        if row["window_shortfall"]
    )
    a036 = rows["A036"]
    assert (a036["nights_required"], a036["window_weeks"]) == (7, 5)
    assert a036["window_shortfall"] == 2
    assert a036["shortfall_with_eclo"] == 0
    assert a036["primary_factor"] == "window"
    assert "structural" in a036["summary"]


def test_explanations_rank_by_weighted_cost(instance, schedule_a):
    rows = explain_delays(instance, schedule_a)
    costs = [row["weighted_cost"] for row in rows]
    assert costs == sorted(costs, reverse=True)
    # Scenario A's whole objective is these two activities' delay cost.
    assert sum(costs) == pytest.approx(measure(instance, "A", schedule_a))


def test_levers_are_proposed_only_where_evidence_exists(instance, schedule_a):
    explanations = explain_delays(instance, schedule_a)
    levers = candidate_levers(instance, explanations, limit=1000)
    assert levers, "a delayed schedule should propose at least one lever"
    # Both window shortfalls need earlier starts, but another high-cost delay
    # may put its capacity remedy ahead of one of them in the global ranking.
    proposed = {(lever.kind, lever.target) for lever in levers}
    assert {("start_date", "A036"), ("start_date", "A059")} <= proposed

    for lever in levers:
        if lever.kind == "start_date":
            assert any(
                row["activity_id"] == lever.target and row["window_shortfall"]
                for row in explanations
            )
        elif lever.kind in {"weekly_access", "workfronts"}:
            factor = "allocation" if lever.kind == "weekly_access" else "workfront"
            assert any(
                f"{row['contract_number']}/{row['activity_type']}" == lever.target
                and row["blocking_factors"][factor]
                for row in explanations
            )
        else:
            assert lever.kind == "supply"
            assert any(
                hotspot["location_id"] == lever.target
                for row in explanations
                for hotspot in row["hotspots"]
            )


def test_apply_lever_does_not_mutate_the_original(instance):
    lever = Lever("weekly_access", "C006/Construction", "d", "c")
    before = [c.number_of_maximum_access_per_week for c in instance.contracts]
    changed = apply_lever(instance, lever)
    assert [c.number_of_maximum_access_per_week for c in instance.contracts] == before
    assert (
        sum(c.number_of_maximum_access_per_week for c in changed.contracts)
        == sum(before) + 1
    )


def test_supply_and_start_date_levers_apply(instance):
    location = instance.locations[0].location_id
    raised = apply_lever(instance, Lever("supply", location, "d", "c"))
    original = next(x for x in instance.locations if x.location_id == location)
    lifted = next(x for x in raised.locations if x.location_id == location)
    assert lifted.supply_capacity == original.supply_capacity + 1

    pulled = apply_lever(instance, Lever("start_date", "A036", "d", "c", magnitude=2))
    before = next(a for a in instance.activities if a.activity_id == "A036")
    after = next(a for a in pulled.activities if a.activity_id == "A036")
    assert (before.planned_start_date - after.planned_start_date).days == 14


def test_unknown_lever_kind_is_rejected(instance):
    with pytest.raises(ValueError, match="Unknown lever"):
        apply_lever(instance, Lever("teleport", "A036", "d", "c"))


def test_start_date_lever_recovers_the_structural_delay(instance, schedule_a):
    """The counterfactual has to back the diagnosis with a re-solve."""
    baseline = measure(instance, "A", schedule_a)
    lever = Lever("start_date", "A036", "d", "c", magnitude=2)
    [result] = cheapest_unlocks(instance, "A", [lever], baseline, time_limit_seconds=90)
    assert result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    # The exact saving moves with the buffer reading; the direction must not.
    assert result["objective_after"] < baseline
    assert result["objective_delta"] < 0
