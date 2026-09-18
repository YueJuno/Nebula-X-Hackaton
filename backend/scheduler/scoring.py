"""Soft scores and the section 2.5 objective. Scoring never decides feasibility."""

from scheduler.domain import Instance
from scheduler.objectives import ACTIVITY_MULTIPLIERS, CONTRACT_WEIGHTS, SCORE_SCALE
from scheduler.policies import Policy
from scheduler.rules import Index

FORMULA_VERSION = "ps1-2.5"


def completion_table(index: Index) -> dict:
    """Per-contract completion, taken from the schedule rather than from RESULTS.csv."""
    instance: Instance = index.instance
    rows = {}
    for contract_number in sorted({c.contract_number for c in instance.contracts}):
        weeks = [
            row.week
            for activity in instance.activities
            if activity.contract_number == contract_number
            for row in index.accesses[activity.activity_id]
        ]
        records = [c for c in instance.contracts if c.contract_number == contract_number]
        # A contract may span several activity types; the tightest date and the
        # strongest priority across its rows govern the contract as a whole.
        deadline = min(record.planned_completion_date for record in records)
        priority = min(record.contract_priority for record in records)
        if not weeks:
            rows[contract_number] = {
                "contract_number": contract_number,
                "completion_week": None,
                "simulated_completion_date": None,
                "planned_completion_date": deadline.isoformat(),
                "overrun_days": 0,
                "earliness_days": 0,
                "contract_priority": priority,
            }
            continue
        completion = instance.week_end(max(weeks))
        rows[contract_number] = {
            "contract_number": contract_number,
            "completion_week": max(weeks),
            "simulated_completion_date": completion.isoformat(),
            "planned_completion_date": deadline.isoformat(),
            "overrun_days": max(0, (completion - deadline).days),
            "earliness_days": max(0, (deadline - completion).days),
            "contract_priority": priority,
        }
    return rows


def capacity_usage(index: Index) -> tuple[int, list]:
    """Possessions booked per location-week against nominal LOCATION_SUPPLY."""
    instance = index.instance
    total, hotspots = 0, []
    for location in sorted(instance.locations, key=lambda item: item.location_id):
        for week in range(1, instance.horizon_weeks + 1):
            used = len(index.groups_at[location.location_id, week])
            if not used:
                continue
            excess = max(0, used - location.supply_capacity)
            total += excess
            if used >= location.supply_capacity:
                hotspots.append(
                    {
                        "location_id": location.location_id,
                        "week": week,
                        "possessions": used,
                        "nominal_supply": location.supply_capacity,
                        "excess": excess,
                    }
                )
    return total, hotspots


def priority_weighted_score(index: Index) -> float:
    """Contract tier sets the band; activity_priority only nudges inside it."""
    instance = index.instance
    scaled = 0
    for activity in instance.activities:
        rows = index.accesses[activity.activity_id]
        if not rows:
            continue
        contract = instance.contract_for(activity)
        completion = instance.week_end(max(row.week for row in rows))
        late = max(0, (completion - contract.planned_completion_date).days)
        scaled += (
            CONTRACT_WEIGHTS[contract.contract_priority]
            * ACTIVITY_MULTIPLIERS[activity.activity_priority]
            * late
        )
    return scaled / SCORE_SCALE


def score_submission(index: Index, policy: Policy, completion: dict) -> tuple[dict, dict]:
    """Return (soft_scores, detail) for the section 2.7 report."""
    excess_total, hotspots = capacity_usage(index)
    eclo_total = sum(row.eclo for rows in index.accesses.values() for row in rows)
    nights = sum(len(rows) for rows in index.accesses.values())
    overrun = {
        tier: sum(
            row["overrun_days"]
            for row in completion.values()
            if row["contract_priority"] == int(tier)
        )
        for tier in ("1", "2", "3")
    }
    soft_scores = {
        "scenario": policy.scenario,
        "overrun_days_total": sum(row["overrun_days"] for row in completion.values()),
        "contracts_overrunning": sum(
            row["overrun_days"] > 0 for row in completion.values()
        ),
        "earliness_days_total": sum(
            row["earliness_days"] for row in completion.values()
        ),
        "excess_access_nights_total": excess_total,
        "eclo_nights_total": eclo_total,
        "priority_overrun": overrun,
        "priority_weighted_score": priority_weighted_score(index),
    }
    detail = {
        "capacity_hotspots": hotspots,
        "nights_scheduled": nights,
        "eclo_nights": eclo_total,
    }
    return soft_scores, detail


def objective_score(soft_scores: dict, policy: Policy) -> float:
    """Section 2.5: A scores overrun, B scores what it spent, C carries both."""
    total = 0.0
    if policy.score_delay:
        total += soft_scores["priority_weighted_score"]
    if policy.score_excess:
        total += 7 * soft_scores["excess_access_nights_total"]
    if policy.allow_eclo:
        total += 5 * soft_scores["eclo_nights_total"]
    return round(total, 4)
