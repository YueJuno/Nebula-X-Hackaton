from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from scheduler.domain import Instance
from scheduler.topology import Footprint


@dataclass
class Variables:
    access: dict = field(default_factory=dict)
    eclo: dict = field(default_factory=dict)
    night: dict = field(default_factory=dict)
    possession: dict = field(default_factory=dict)
    lateness: dict = field(default_factory=dict)
    excess: dict = field(default_factory=dict)


def create_variables(
    model: cp_model.CpModel, instance: Instance, footprints: dict[str, Footprint]
) -> Variables:
    variables = Variables()
    max_groups = len(instance.activities)
    end = instance.week_end(instance.horizon_weeks)
    for activity in instance.activities:
        contract = instance.contract_for(activity)
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
            for location in footprints[activity.activity_id].occupied:
                variables.possession[activity.activity_id, week, location] = (
                    model.new_int_var(
                        1, max_groups, f"group_{activity.activity_id}_{week}_{location}"
                    )
                )
    for location in instance.locations:
        for week in range(1, instance.horizon_weeks + 1):
            variables.excess[location.location_id, week] = model.new_int_var(
                0, max_groups, f"excess_{location.location_id}_{week}"
            )
    return variables
