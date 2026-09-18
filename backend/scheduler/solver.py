"""Model orchestration; never solve without the railway constraint modules."""

from ortools.sat.python import cp_model

from scheduler.constraints import apply_constraints, missing_constraints
from scheduler.objectives import set_objective
from scheduler.policies import get_policy
from scheduler.results import extract_schedule
from scheduler.topology import calculate_footprints
from scheduler.variables import create_variables, maximum_groups


def possession_group_limits(instance, policy):
    full_group_limit = maximum_groups(instance, policy)
    if policy.max_excess_per_location_week is not None:
        return [full_group_limit]
    compact_limit = min(
        full_group_limit,
        max(location.supply_capacity for location in instance.locations) + 8,
    )
    return (
        [compact_limit]
        if compact_limit == full_group_limit
        else [compact_limit, full_group_limit]
    )


def build_model(instance, scenario, max_groups=None):
    model = cp_model.CpModel()
    footprints = calculate_footprints(instance)
    policy = get_policy(scenario)
    variables = create_variables(model, instance, footprints, policy, max_groups)
    set_objective(model, variables, instance, policy)
    return model, variables, footprints, policy


def prepare(instance, scenario):
    policy = get_policy(scenario)
    model, _variables, footprints, policy = build_model(
        instance, scenario, possession_group_limits(instance, policy)[0]
    )
    return {
        "summary": instance.summary(),
        "policy": policy.to_dict(),
        "missing_constraints": missing_constraints(),
        "model_stats": model.model_stats(),
        "footprints": {key: value.model_dump() for key, value in footprints.items()},
        "notice": "Topology and model preparation only. No feasible schedule has been produced.",
    }


def solve(instance, scenario, time_limit_seconds=60):
    # Gate before any search so unconstrained assignments cannot be mistaken for a schedule.
    if missing := missing_constraints():
        raise NotImplementedError("Missing railway constraints: " + ", ".join(missing))
    policy = get_policy(scenario)
    group_limits = possession_group_limits(instance, policy)

    last_status = None
    for index, group_limit in enumerate(group_limits):
        model, variables, footprints, policy = build_model(
            instance, scenario, group_limit
        )
        apply_constraints(model, variables, instance, footprints, policy)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = (
            time_limit_seconds
            if len(group_limits) == 1
            else max(10, time_limit_seconds // len(group_limits))
        )
        solver.parameters.num_search_workers = 8
        status = solver.solve(model)
        last_status = solver.status_name(status)
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            return extract_schedule(solver, variables, instance, status)
        if index + 1 < len(group_limits):
            continue
    raise RuntimeError(f"No complete solution returned: {last_status}")
