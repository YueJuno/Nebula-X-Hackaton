"""Model orchestration; never solve without the railway constraint modules."""

from ortools.sat.python import cp_model

from scheduler.constraints import apply_constraints, missing_constraints
from scheduler.objectives import set_objective
from scheduler.policies import get_policy
from scheduler.results import extract_schedule
from scheduler.topology import calculate_footprints
from scheduler.variables import create_variables


def build_model(instance, scenario):
    model = cp_model.CpModel()
    footprints = calculate_footprints(instance)
    policy = get_policy(scenario)
    variables = create_variables(model, instance, footprints)
    set_objective(model, variables, instance, policy)
    return model, variables, footprints, policy


def prepare(instance, scenario):
    model, _variables, footprints, policy = build_model(instance, scenario)
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
    model, variables, footprints, policy = build_model(instance, scenario)
    apply_constraints(model, variables, instance, footprints, policy)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise RuntimeError(
            f"No complete solution returned: {solver.status_name(status)}"
        )
    return extract_schedule(solver, variables, instance)
