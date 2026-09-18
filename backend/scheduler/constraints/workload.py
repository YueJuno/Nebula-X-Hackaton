"""Workload conservation, release dates, frequency and predecessor ordering."""

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    for activity in instance.activities:
        accesses = [
            variables.access[activity.activity_id, week]
            for week in range(1, instance.horizon_weeks + 1)
        ]
        eclo = [
            variables.eclo[activity.activity_id, week]
            for week in range(1, instance.horizon_weeks + 1)
        ]

        # Work in half-access units: a normal night contributes 2, ECLO adds 1.
        delivered = 2 * sum(accesses) + sum(eclo)
        required = 2 * activity.total_accesses
        model.add(delivered >= required)
        # Permit the unavoidable half-access overshoot, but no gratuitous work.
        model.add(delivered <= required + 1)

        for week in range(1, instance.horizon_weeks + 1):
            access = variables.access[activity.activity_id, week]
            if instance.week_start(week) < activity.planned_start_date:
                model.add(access == 0)

        predecessor_id = activity.predecessor_activity_id
        if not predecessor_id:
            continue
        # Every predecessor access must finish before the successor starts.
        for successor_week in range(1, instance.horizon_weeks + 1):
            successor = variables.access[activity.activity_id, successor_week]
            for predecessor_week in range(
                successor_week, instance.horizon_weeks + 1
            ):
                predecessor = variables.access[
                    predecessor_id, predecessor_week
                ]
                model.add(successor + predecessor <= 1)
