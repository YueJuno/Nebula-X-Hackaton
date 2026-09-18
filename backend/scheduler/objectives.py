"""Integer-scaled penalties. Constraint modules must link accounting variables."""

from scheduler.domain import Instance
from scheduler.policies import Policy

SCORE_SCALE = 10
CONTRACT_WEIGHTS = {1: 100, 2: 10, 3: 1}
ACTIVITY_MULTIPLIERS = {1: 13, 2: 12, 3: 10}


def delay_coefficient(contract_priority: int, activity_priority: int) -> int:
    return CONTRACT_WEIGHTS[contract_priority] * ACTIVITY_MULTIPLIERS[activity_priority]


def set_objective(model, variables, instance: Instance, policy: Policy):
    terms = []
    if policy.score_delay:
        for activity in instance.activities:
            terms.append(
                delay_coefficient(
                    instance.contract_for(activity).contract_priority,
                    activity.activity_priority,
                )
                * variables.lateness[activity.activity_id]
            )
    if policy.score_excess:
        terms.extend(
            7 * SCORE_SCALE * variable for variable in variables.excess.values()
        )
    if policy.allow_eclo:
        terms.extend(5 * SCORE_SCALE * variable for variable in variables.eclo.values())
    model.minimize(sum(terms))
