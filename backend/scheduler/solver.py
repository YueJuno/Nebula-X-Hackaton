"""Model orchestration; never solve without the railway constraint modules."""

from ortools.sat.python import cp_model

from scheduler.constraints import apply_constraints, missing_constraints
from scheduler.objectives import SCORE_SCALE, set_objective
from scheduler.policies import get_policy
from scheduler.results import extract_schedule
from scheduler.topology import calculate_footprints
from scheduler.variables import create_variables, maximum_groups


def possession_group_limits(instance, policy):
    full_group_limit = maximum_groups(instance, policy)
    if policy.max_excess_per_location_week is not None:
        return [full_group_limit]
    nominal_limit = max(location.supply_capacity for location in instance.locations)
    compact_limit = min(
        full_group_limit,
        nominal_limit + 4,
    )
    return list(dict.fromkeys([nominal_limit, compact_limit, full_group_limit]))


def _omitted_solution_penalty(instance, group_limit):
    nominal_limit = max(location.supply_capacity for location in instance.locations)
    minimum_excess = group_limit + 1 - nominal_limit
    return 7 * SCORE_SCALE * minimum_excess


def build_model(instance, scenario, max_groups=None, buffer_granularity="week"):
    model = cp_model.CpModel()
    footprints = calculate_footprints(instance)
    policy = get_policy(scenario, buffer_granularity)
    variables = create_variables(model, instance, footprints, policy, max_groups)
    set_objective(model, variables, instance, policy)
    return model, variables, footprints, policy


def prepare(instance, scenario, buffer_granularity="week"):
    policy = get_policy(scenario, buffer_granularity)
    model, _variables, footprints, policy = build_model(
        instance,
        scenario,
        possession_group_limits(instance, policy)[0],
        buffer_granularity,
    )
    return {
        "summary": instance.summary(),
        "policy": policy.to_dict(),
        "missing_constraints": missing_constraints(),
        "model_stats": model.model_stats(),
        "footprints": {key: value.model_dump() for key, value in footprints.items()},
        "notice": "Topology and model preparation only. No feasible schedule has been produced.",
    }


def solve(instance, scenario, time_limit_seconds=60, buffer_granularity="week"):
    # Gate before any search so unconstrained assignments cannot be mistaken for a schedule.
    if missing := missing_constraints():
        raise NotImplementedError("Missing railway constraints: " + ", ".join(missing))
    policy = get_policy(scenario, buffer_granularity)
    group_limits = possession_group_limits(instance, policy)

    last_status = None
    for index, group_limit in enumerate(group_limits):
        model, variables, footprints, policy = build_model(
            instance, scenario, group_limit, buffer_granularity
        )
        apply_constraints(model, variables, instance, footprints, policy)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 8
        status = solver.solve(model)
        last_status = solver.status_name(status)
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            schedule = extract_schedule(solver, variables, instance, status)
            full_domain = group_limit == group_limits[-1]
            omitted_domain_cannot_improve = (
                status == cp_model.OPTIMAL
                and policy.score_excess
                and solver.objective_value
                <= _omitted_solution_penalty(instance, group_limit)
            )
            if status == cp_model.OPTIMAL and (
                full_domain or omitted_domain_cannot_improve
            ):
                return schedule
            # A restricted Scenario B domain can prove its own optimum without
            # proving that buying more groups cannot improve the global score.
            return schedule.model_copy(update={"solver_status": "FEASIBLE"})
        if index + 1 < len(group_limits):
            continue
    raise RuntimeError(f"No complete solution returned: {last_status}")
