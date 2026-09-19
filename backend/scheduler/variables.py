from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from scheduler.domain import Instance
from scheduler.policies import Policy
from scheduler.topology import Footprint


@dataclass
class Variables:
    max_groups: int = 0
    access: dict = field(default_factory=dict)
    eclo: dict = field(default_factory=dict)
    night: dict = field(default_factory=dict)
    on_night: dict = field(default_factory=dict)
    possession: dict = field(default_factory=dict)
    closure_group: dict = field(default_factory=dict)
    in_group: dict = field(default_factory=dict)
    group_used: dict = field(default_factory=dict)
    completion_week: dict = field(default_factory=dict)
    eclo_window_start: dict = field(default_factory=dict)
    lateness: dict = field(default_factory=dict)
    excess: dict = field(default_factory=dict)


def maximum_groups(instance: Instance, policy: Policy) -> int:
    if policy.max_excess_per_location_week is not None:
        return (
            max(location.supply_capacity for location in instance.locations)
            + policy.max_excess_per_location_week
        )

    # Scenario B may buy extra possessions. It can never need more groups at a
    # location than the number of activity accesses permitted in one week.
    grouped = {}
    for activity in instance.activities:
        grouped.setdefault(
            (activity.contract_number, activity.activity_type), []
        ).append(activity)
    weekly_event_bound = min(
        len(instance.activities),
        sum(
            min(
                len(activities),
                instance.contract_for(activities[0]).number_of_maximum_access_per_week
                * instance.contract_for(activities[0]).number_of_workfronts,
            )
            for activities in grouped.values()
        ),
    )
    return weekly_event_bound


def create_variables(
    model: cp_model.CpModel,
    instance: Instance,
    footprints: dict[str, Footprint],
    policy: Policy,
    max_groups: int | None = None,
) -> Variables:
    max_groups = max_groups or maximum_groups(instance, policy)
    variables = Variables(max_groups=max_groups)
    end = instance.week_end(instance.horizon_weeks)
    for activity in instance.activities:
        contract = instance.contract_for(activity)
        variables.completion_week[activity.activity_id] = model.new_int_var(
            1, instance.horizon_weeks, f"completion_{activity.activity_id}"
        )
        variables.lateness[activity.activity_id] = model.new_int_var(
            0,
            max(0, (end - contract.planned_completion_date).days),
            f"late_{activity.activity_id}",
        )
        for week in range(1, instance.horizon_weeks + 1):
            key = activity.activity_id, week
            variables.access[key] = model.new_bool_var(
                f"access_{activity.activity_id}_{week}"
            )
            variables.eclo[key] = model.new_bool_var(
                f"eclo_{activity.activity_id}_{week}"
            )
            variables.night[key] = model.new_int_var(
                1,
                contract.number_of_maximum_access_per_week,
                f"night_{activity.activity_id}_{week}",
            )
            for night in range(1, contract.number_of_maximum_access_per_week + 1):
                variables.on_night[activity.activity_id, week, night] = (
                    model.new_bool_var(
                        f"on_night_{activity.activity_id}_{week}_{night}"
                    )
                )
            for location in footprints[activity.activity_id].occupied:
                variables.possession[activity.activity_id, week, location] = (
                    model.new_int_var(
                        1, max_groups, f"group_{activity.activity_id}_{week}_{location}"
                    )
                )
                for group in range(1, max_groups + 1):
                    variables.in_group[activity.activity_id, week, location, group] = (
                        model.new_bool_var(
                            f"in_group_{activity.activity_id}_{week}_{location}_{group}"
                        )
                    )
            footprint = footprints[activity.activity_id]
            closure_locations = set(
                footprint.occupied
                + footprint.buffers
                + footprint.mirrored
                + footprint.cross_line
            )
            for location in closure_locations:
                key = activity.activity_id, week, location
                if key in variables.possession:
                    variables.closure_group[key] = variables.possession[key]
                else:
                    variables.closure_group[key] = model.new_int_var(
                        1,
                        max_groups,
                        f"closure_group_{activity.activity_id}_{week}_{location}",
                    )
    for location in instance.locations:
        for week in range(1, instance.horizon_weeks + 1):
            variables.excess[location.location_id, week] = model.new_int_var(
                0, max_groups, f"excess_{location.location_id}_{week}"
            )
    for line in instance.lines:
        variables.eclo_window_start[line.line_code] = model.new_int_var(
            1, instance.horizon_weeks, f"eclo_window_start_{line.line_code}"
        )
    return variables
