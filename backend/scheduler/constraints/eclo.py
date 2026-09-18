"""ECLO linkage, scenario prohibition and per-line continuity windows."""

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    for activity in instance.activities:
        footprint = footprints[activity.activity_id]
        for week in range(1, instance.horizon_weeks + 1):
            eclo = variables.eclo[activity.activity_id, week]
            access = variables.access[activity.activity_id, week]
            model.add(eclo <= access)
            if not policy.allow_eclo:
                model.add(eclo == 0)
            if policy.eclo_window_weeks:
                for line in footprint.affected_lines:
                    start = variables.eclo_window_start[line]
                    model.add(start <= week).only_enforce_if(eclo)
                    model.add(
                        week < start + policy.eclo_window_weeks
                    ).only_enforce_if(eclo)
