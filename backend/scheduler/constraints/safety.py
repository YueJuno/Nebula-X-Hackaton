"""Buffers, opposite-bound mirroring and interchange conflict rules."""

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    activities = instance.activities

    def closure(activity_id):
        footprint = footprints[activity_id]
        return set(
            footprint.occupied
            + footprint.buffers
            + footprint.mirrored
            + footprint.cross_line
        )

    for index, first in enumerate(activities):
        first_footprint = footprints[first.activity_id]
        first_closure = closure(first.activity_id)
        first_anchor = first_footprint.occupied[0]
        for second in activities[index + 1 :]:
            second_footprint = footprints[second.activity_id]
            second_closure = closure(second.activity_id)
            if first_closure.isdisjoint(second_closure):
                continue

            # A common occupied location with the same group is an intentional
            # co-share; the possession module enforces its PM/PC/C legal mix.
            if not set(first_footprint.occupied).isdisjoint(
                second_footprint.occupied
            ):
                continue

            second_anchor = second_footprint.occupied[0]
            for week in range(1, instance.horizon_weeks + 1):
                model.add(
                    variables.possession[
                        first.activity_id, week, first_anchor
                    ]
                    != variables.possession[
                        second.activity_id, week, second_anchor
                    ]
                ).only_enforce_if(
                    [
                        variables.access[first.activity_id, week],
                        variables.access[second.activity_id, week],
                    ]
                )
