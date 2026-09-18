from dataclasses import asdict, dataclass
from typing import Literal

Scenario = Literal["A", "B", "C"]


@dataclass(frozen=True)
class Policy:
    scenario: Scenario
    allow_eclo: bool
    fixed_deadlines: bool
    max_excess_per_location_week: int | None
    eclo_window_weeks: int | None
    score_delay: bool
    score_excess: bool

    def to_dict(self):
        return asdict(self)


def get_policy(scenario: Scenario) -> Policy:
    policies = {
        "A": Policy("A", False, False, 0, None, True, False),
        "B": Policy("B", True, True, None, None, False, True),
        "C": Policy("C", True, False, 1, 2, True, True),
    }
    return policies[scenario]
