"""Why an activity is late, and what the cheapest way to fix it would be.

Two layers, deliberately separated by cost:

* ``explain_delays`` reads one solved schedule and attributes every week an
  overrunning activity could have used but did not. No re-solving, so it is
  cheap enough to run inside a web request.
* ``cheapest_unlocks`` re-solves the instance once per candidate lever and
  ranks the levers by how much objective they buy back. Minutes, not
  milliseconds, so it belongs in the CLI or a background job.

The levers are deliberately operational rather than mathematical: one more
access-night a week, one more workfront, or one more possession at a location
are all things a planner can actually go and negotiate.
"""

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from scheduler.domain import Instance
from scheduler.exporter import export_files
from scheduler.objectives import ACTIVITY_MULTIPLIERS, CONTRACT_WEIGHTS, SCORE_SCALE
from scheduler.policies import get_policy
from scheduler.results import Schedule
from scheduler.rules import week_of
from scheduler.scoring import objective_score
from scheduler.validator import validate_files

FACTORS = ("window", "allocation", "workfront", "capacity", "predecessor")


@dataclass(frozen=True)
class Lever:
    """One negotiable change to the instance."""

    kind: str
    target: str
    description: str
    cost_note: str
    magnitude: int = 1

    def to_dict(self):
        return {
            "kind": self.kind,
            "target": self.target,
            "description": self.description,
            "cost_note": self.cost_note,
            "magnitude": self.magnitude,
        }


class Usage:
    """Per-week consumption of the things that ration access."""

    def __init__(self, instance: Instance, schedule: Schedule):
        activities = {item.activity_id: item for item in instance.activities}
        self.nights = defaultdict(set)
        self.fronts = defaultdict(set)
        self.possessions = defaultdict(set)
        self.weeks = defaultdict(set)
        for access in schedule.accesses:
            activity = activities[access.activity_id]
            key = (activity.contract_number, activity.activity_type, access.week)
            self.nights[key].add(access.access_night)
            self.fronts[key + (access.access_night,)].add(access.activity_id)
            self.weeks[access.activity_id].add(access.week)
            for location_id, group in access.groups.items():
                self.possessions[location_id, access.week].add(group)


def explain_delays(instance: Instance, schedule: Schedule) -> list[dict]:
    """Attribute each overrunning activity's slip to the weeks it could not use."""
    usage = Usage(instance, schedule)
    supply = {item.location_id: item.supply_capacity for item in instance.locations}
    footprint_of = {
        access.activity_id: sorted(access.groups) for access in schedule.accesses
    }
    explanations = []

    for activity in instance.activities:
        weeks = usage.weeks.get(activity.activity_id, set())
        if not weeks:
            continue
        contract = instance.contract_for(activity)
        completion = instance.week_end(max(weeks))
        overrun = max(0, (completion - contract.planned_completion_date).days)
        if not overrun:
            continue

        earliest = week_of(instance, activity.planned_start_date)
        deadline_week = week_of(instance, contract.planned_completion_date)
        key = (activity.contract_number, activity.activity_type)
        predecessor_end = max(
            usage.weeks.get(activity.predecessor_activity_id, {0}), default=0
        )

        # An activity gets at most one access-night a week, so a window shorter
        # than its workload cannot be met at all. That is structural: no amount
        # of supply, workfront or allocation relief touches it, and it dominates
        # every other factor when present.
        window = deadline_week - earliest + 1
        shortfall = max(0, activity.total_accesses - window)
        with_eclo = max(0, ceil(activity.total_accesses / 1.5) - window)

        factors = dict.fromkeys(FACTORS, 0)
        factors["window"] = shortfall
        missed, hotspots = [], defaultdict(list)
        for week in range(earliest, deadline_week + 1):
            if week in weeks:
                continue
            missed.append(week)
            if activity.predecessor_activity_id and week <= predecessor_end:
                factors["predecessor"] += 1
                continue
            booked_nights = usage.nights[key + (week,)]
            granted = contract.number_of_maximum_access_per_week
            if len(booked_nights) >= granted:
                # The contract's weekly budget was already spent that week; a
                # free workfront on one of those nights would still have served.
                if all(
                    len(usage.fronts[key + (week, night)])
                    >= contract.number_of_workfronts
                    for night in booked_nights
                ):
                    factors["workfront"] += 1
                else:
                    factors["allocation"] += 1
            saturated = [
                location_id
                for location_id in footprint_of.get(activity.activity_id, [])
                if len(usage.possessions[location_id, week])
                >= supply.get(location_id, 0)
            ]
            if saturated:
                factors["capacity"] += 1
                for location_id in saturated:
                    hotspots[location_id].append(week)

        weighted = (
            CONTRACT_WEIGHTS[contract.contract_priority]
            * ACTIVITY_MULTIPLIERS[activity.activity_priority]
            * overrun
            / SCORE_SCALE
        )
        ranked = sorted(
            ((name, count) for name, count in factors.items() if count),
            key=lambda pair: -pair[1],
        )
        explanations.append(
            {
                "activity_id": activity.activity_id,
                "contract_number": activity.contract_number,
                "activity_type": activity.activity_type,
                "contract_priority": contract.contract_priority,
                "activity_priority": activity.activity_priority,
                "completion_week": max(weeks),
                "deadline_week": deadline_week,
                "overrun_days": overrun,
                "weighted_cost": round(weighted, 2),
                "earliest_week": earliest,
                "window_weeks": window,
                "nights_required": activity.total_accesses,
                "window_shortfall": shortfall,
                "shortfall_with_eclo": with_eclo,
                "missed_weeks": missed,
                "blocking_factors": factors,
                "primary_factor": "window"
                if shortfall
                else (ranked[0][0] if ranked else "none"),
                "hotspots": [
                    {"location_id": location_id, "weeks": sorted(set(weeks_hit))}
                    for location_id, weeks_hit in sorted(hotspots.items())
                ],
                "summary": summarize(
                    activity.activity_id,
                    overrun,
                    ranked,
                    hotspots,
                    activity.total_accesses,
                    window,
                    shortfall,
                    with_eclo,
                ),
            }
        )
    return sorted(explanations, key=lambda row: -row["weighted_cost"])


def summarize(
    activity_id, overrun, ranked, hotspots, required, window, shortfall, with_eclo
) -> str:
    if shortfall:
        relief = (
            "ECLO nights would still leave it "
            f"{with_eclo} week{'s' if with_eclo != 1 else ''} short"
            if with_eclo
            else "ECLO nights would close the gap where the scenario permits them"
        )
        return (
            f"{activity_id} overruns by {overrun} days for a structural reason: it needs "
            f"{required} access-nights but its planned start and deadline leave a "
            f"{window}-week window, and an activity may take only one night a week. "
            f"It is {shortfall} week{'s' if shortfall != 1 else ''} short before any "
            f"contention is considered, so no extra supply, workfront or weekly "
            f"allocation can recover it. {relief}."
        )
    if not ranked:
        return (
            f"{activity_id} overruns by {overrun} days with no blocked week before its "
            "deadline and no window shortfall; check contention on its span."
        )
    phrases = {
        "allocation": "its contract's weekly access-night budget was already spent",
        "workfront": "its contract had no free workfront on the nights it held",
        "capacity": "the locations on its span were at nominal supply",
        "predecessor": "its predecessor had not finished",
    }
    lead = ", ".join(f"{phrases[name]} ({count} wks)" for name, count in ranked[:2])
    where = ""
    if hotspots:
        busiest = max(hotspots.items(), key=lambda pair: len(pair[1]))
        where = (
            f" Tightest location: {busiest[0]} ({len(set(busiest[1]))} wks at supply)."
        )
    return f"{activity_id} overruns by {overrun} days because {lead}.{where}"


def candidate_levers(
    instance: Instance, explanations: list[dict], limit: int = 6
) -> list[Lever]:
    """Turn the blocking factors into the changes most likely to buy relief."""
    contracts = {
        (item.contract_number, item.activity_type): item for item in instance.contracts
    }
    allocation, workfront, capacity = (
        defaultdict(float),
        defaultdict(float),
        defaultdict(float),
    )
    for row in explanations:
        # Weight every candidate by the delay cost it would relieve, so a
        # Priority-1 blocker outranks a long tail of Priority-3 ones.
        weight = row["weighted_cost"]
        key = (row["contract_number"], row["activity_type"])
        allocation[key] += weight * row["blocking_factors"]["allocation"]
        workfront[key] += weight * row["blocking_factors"]["workfront"]
        for hotspot in row["hotspots"]:
            capacity[hotspot["location_id"]] += weight * len(hotspot["weeks"])

    levers = []
    for row in explanations:
        if not row["window_shortfall"]:
            continue
        weeks = row["window_shortfall"]
        levers.append(
            (
                # Only an earlier start can remove this activity's window
                # shortfall. Global ranking still weighs all delayed work.
                row["weighted_cost"] * (weeks + 1) * 10,
                Lever(
                    kind="start_date",
                    target=row["activity_id"],
                    description=f"Bring {row['activity_id']} forward {weeks} week"
                    f"{'s' if weeks != 1 else ''} so its "
                    f"{row['nights_required']} access-nights fit before its deadline.",
                    cost_note="Earlier mobilisation for one activity; no extra track access.",
                    magnitude=weeks,
                ),
            )
        )
    for key, score in allocation.items():
        contract = contracts[key]
        levers.append(
            (
                score,
                Lever(
                    kind="weekly_access",
                    target=f"{key[0]}/{key[1]}",
                    description=f"Grant {key[0]} ({key[1]}) one more access-night per week "
                    f"({contract.number_of_maximum_access_per_week} to "
                    f"{contract.number_of_maximum_access_per_week + 1}).",
                    cost_note="One extra weekly access-night to negotiate with the contractor.",
                ),
            )
        )
    for key, score in workfront.items():
        contract = contracts[key]
        levers.append(
            (
                score,
                Lever(
                    kind="workfronts",
                    target=f"{key[0]}/{key[1]}",
                    description=f"Give {key[0]} ({key[1]}) one more concurrent workfront "
                    f"({contract.number_of_workfronts} to "
                    f"{contract.number_of_workfronts + 1}).",
                    cost_note="One extra crew working the same night.",
                ),
            )
        )
    for location_id, score in capacity.items():
        levers.append(
            (
                score,
                Lever(
                    kind="supply",
                    target=location_id,
                    description=f"Release one more possession per week at {location_id}.",
                    cost_note="One extra access-night per week at a single location.",
                ),
            )
        )
    # A lever with no evidence behind it cannot buy anything, and each one costs
    # a full re-solve, so only ranked candidates are worth trying.
    levers = [pair for pair in levers if pair[0] > 0]
    levers.sort(key=lambda pair: -pair[0])
    return [lever for _score, lever in levers[:limit]]


def apply_lever(instance: Instance, lever: Lever) -> Instance:
    changed = deepcopy(instance)
    if lever.kind in {"weekly_access", "workfronts"}:
        number, activity_type = lever.target.split("/", 1)
        for contract in changed.contracts:
            if (contract.contract_number, contract.activity_type) != (
                number,
                activity_type,
            ):
                continue
            if lever.kind == "weekly_access":
                contract.number_of_maximum_access_per_week += 1
            else:
                contract.number_of_workfronts += 1
    elif lever.kind == "supply":
        for location in changed.locations:
            if location.location_id == lever.target:
                location.supply_capacity += 1
    elif lever.kind == "start_date":
        for activity in changed.activities:
            if activity.activity_id == lever.target:
                activity.planned_start_date = max(
                    changed.horizon_start,
                    activity.planned_start_date - timedelta(weeks=lever.magnitude),
                )
    else:
        raise ValueError(f"Unknown lever kind {lever.kind}")
    return changed


def measure(instance: Instance, scenario: str, schedule: Schedule) -> float:
    """Score a schedule by the section 2.5 formula, feasible or not."""
    report = validate_files(instance, export_files(instance, schedule, scenario))
    scores = report.get("soft_scores") or {}
    if not scores:
        return float("inf")
    return objective_score(scores, get_policy(scenario))


def cheapest_unlocks(
    instance: Instance,
    scenario: str,
    levers: list[Lever],
    baseline: float,
    time_limit_seconds: int = 30,
) -> list[dict]:
    """Re-solve once per lever and rank them by objective bought back."""
    from scheduler.solver import solve  # Imported late to keep OR-Tools optional.

    results = []
    for lever in levers:
        row = {"lever": lever.to_dict(), "objective_before": baseline}
        try:
            relaxed = apply_lever(instance, lever)
            schedule = solve(relaxed, scenario, time_limit_seconds)
            after = measure(relaxed, scenario, schedule)
            row.update(
                {
                    "objective_after": after,
                    "objective_delta": round(after - baseline, 4),
                    "solver_status": schedule.solver_status,
                }
            )
        except (RuntimeError, NotImplementedError, ValueError) as exc:
            row.update(
                {
                    "objective_after": None,
                    "objective_delta": None,
                    "solver_status": f"unavailable: {type(exc).__name__}",
                }
            )
        results.append(row)
    return sorted(
        results,
        key=lambda item: (item["objective_delta"] is None, item["objective_delta"]),
    )


def explain(
    instance: Instance,
    scenario: str,
    schedule: Schedule,
    *,
    with_levers: bool = False,
    limit: int = 6,
    time_limit_seconds: int = 30,
) -> dict:
    explanations = explain_delays(instance, schedule)
    report = {
        "scenario": scenario,
        "objective_score": measure(instance, scenario, schedule),
        "delayed_activities": len(explanations),
        "explanations": explanations,
    }
    if not with_levers:
        return report
    levers = candidate_levers(instance, explanations, limit)
    report["levers_tried"] = [lever.to_dict() for lever in levers]
    report["cheapest_unlocks"] = cheapest_unlocks(
        instance, scenario, levers, report["objective_score"], time_limit_seconds
    )
    return report
