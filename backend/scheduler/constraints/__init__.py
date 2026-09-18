"""Extension points only. No railway constraints are implemented."""

from scheduler.constraints import contracts, eclo, possessions, safety, workload

MODULES = (workload, safety, possessions, contracts, eclo)


def missing_constraints() -> list[str]:
    return [
        module.__name__.rsplit(".", 1)[-1]
        for module in MODULES
        if not module.IMPLEMENTED
    ]


def apply_constraints(model, variables, instance, footprints, policy):
    if missing := missing_constraints():
        raise NotImplementedError("Missing railway constraints: " + ", ".join(missing))
    for module in MODULES:
        module.add_constraints(model, variables, instance, footprints, policy)
