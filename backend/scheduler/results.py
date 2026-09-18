from pydantic import BaseModel, Field

from scheduler.domain import Instance


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


def extract_schedule(solver, variables, instance: Instance) -> Schedule:
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
        solver_status=solver.status_name(),
    )
