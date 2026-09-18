from pydantic import BaseModel, Field

from scheduler.domain import Instance
from scheduler.objectives import SCORE_SCALE, delay_coefficient


class Access(BaseModel):
    activity_id: str
    week: int = Field(ge=1)
    eclo: int = Field(ge=0, le=1)
    access_night: int = Field(ge=1)
    groups: dict[str, str]


class Schedule(BaseModel):
    accesses: list[Access]
    objective_score: float
    solver_status: str


def summarize_schedule(instance: Instance, schedule: Schedule) -> dict:
    activities = {activity.activity_id: activity for activity in instance.activities}
    by_activity = {activity_id: [] for activity_id in activities}
    location_groups = {}
    for access in schedule.accesses:
        by_activity[access.activity_id].append(access)
        for location_id, group in access.groups.items():
            location_groups.setdefault((location_id, access.week), set()).add(group)

    locations = {location.location_id: location for location in instance.locations}
    capacity_hotspots = []
    excess_total = 0
    for (location_id, week), groups in sorted(location_groups.items()):
        supply = locations[location_id].supply_capacity
        excess = max(0, len(groups) - supply)
        excess_total += excess
        if len(groups) >= supply:
            capacity_hotspots.append(
                {
                    "location_id": location_id,
                    "week": week,
                    "possessions": len(groups),
                    "nominal_supply": supply,
                    "excess": excess,
                }
            )

    contract_rows = []
    priority_overrun = {"1": 0, "2": 0, "3": 0}
    weighted_delay = 0
    for activity in instance.activities:
        completion_week = max(
            access.week for access in by_activity[activity.activity_id]
        )
        completion = instance.week_end(completion_week)
        contract = instance.contract_for(activity)
        late = max(0, (completion - contract.planned_completion_date).days)
        weighted_delay += (
            delay_coefficient(contract.contract_priority, activity.activity_priority)
            * late
            / SCORE_SCALE
        )

    for contract_number in sorted({c.contract_number for c in instance.contracts}):
        contract_activities = [
            activity
            for activity in instance.activities
            if activity.contract_number == contract_number
        ]
        completion_week = max(
            access.week
            for activity in contract_activities
            for access in by_activity[activity.activity_id]
        )
        completion = instance.week_end(completion_week)
        records = [
            contract
            for contract in instance.contracts
            if contract.contract_number == contract_number
        ]
        deadline = min(contract.planned_completion_date for contract in records)
        priority = min(contract.contract_priority for contract in records)
        overrun = max(0, (completion - deadline).days)
        priority_overrun[str(priority)] += overrun
        contract_rows.append(
            {
                "contract_number": contract_number,
                "completion_week": completion_week,
                "simulated_completion_date": completion.isoformat(),
                "planned_completion_date": deadline.isoformat(),
                "overrun_days": overrun,
                "priority": priority,
            }
        )

    return {
        "solver_status": schedule.solver_status,
        "objective_score": schedule.objective_score,
        "nights_scheduled": len(schedule.accesses),
        "eclo_nights_total": sum(access.eclo for access in schedule.accesses),
        "excess_access_nights_total": excess_total,
        "contracts_overrunning": sum(
            row["overrun_days"] > 0 for row in contract_rows
        ),
        "overrun_days_total": sum(row["overrun_days"] for row in contract_rows),
        "priority_overrun": priority_overrun,
        "priority_weighted_overrun": weighted_delay,
        "capacity_hotspots": capacity_hotspots,
        "contracts": contract_rows,
    }


def extract_schedule(solver, variables, instance: Instance, status) -> Schedule:
    accesses = []
    for (activity_id, week), selected in variables.access.items():
        if solver.value(selected):
            groups = {
                location: f"p{solver.value(variable)}"
                for (aid, w, location), variable in variables.possession.items()
                if (aid, w) == (activity_id, week)
            }
            accesses.append(
                Access(
                    activity_id=activity_id,
                    week=week,
                    eclo=solver.value(variables.eclo[activity_id, week]),
                    access_night=solver.value(variables.night[activity_id, week]),
                    groups=groups,
                )
            )
    return Schedule(
        accesses=accesses,
        objective_score=solver.objective_value / 10,
        solver_status=solver.status_name(status),
    )
