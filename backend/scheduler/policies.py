from dataclasses import asdict, dataclass, replace
from typing import Literal

Scenario = Literal["A", "B", "C"]
# Which activities count as concurrent when buffers are checked. See
# scheduler.rules for why section 2.4 rule 3 admits both readings.
Granularity = Literal["week", "possession"]


@dataclass(frozen=True)
class Policy:
    scenario: Scenario
    allow_eclo: bool
    fixed_deadlines: bool
    max_excess_per_location_week: int | None
    eclo_window_weeks: int | None
    score_delay: bool
    score_excess: bool
    buffer_granularity: Granularity = "week"

    def to_dict(self):
        return asdict(self)


def get_policy(
    scenario: Scenario, buffer_granularity: Granularity = "week"
) -> Policy:
    policies = {
        "A": Policy("A", False, False, 0, None, True, False),
        "B": Policy("B", True, True, None, None, False, True),
        "C": Policy("C", True, False, 1, 2, True, True),
    }
    return replace(policies[scenario], buffer_granularity=buffer_granularity)
