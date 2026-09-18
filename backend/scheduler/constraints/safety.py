"""Buffers, opposite-bound mirroring and interchange conflict rules.

The closure zone is what an activity shuts without booking it, matching
``scheduler.rules``: buffers, the mirrored opposite bound, and the Live
interchange crossover, minus the activity's own occupied span. Two readings of
section 2.4 rule 3 decide which pairs must be kept apart; see
``scheduler.rules`` for why both are defensible.
"""

IMPLEMENTED = True


def closure_zone(footprint):
    return (
        set(footprint.buffers) | set(footprint.mirrored) | set(footprint.cross_line)
    ) - set(footprint.occupied)


def add_constraints(model, variables, instance, footprints, policy):
    activities = instance.activities
    week_strict = policy.buffer_granularity == "week"

    for index, first in enumerate(activities):
        first_footprint = footprints[first.activity_id]
        first_zone = closure_zone(first_footprint)
        first_occupied = set(first_footprint.occupied)
        first_anchor = first_footprint.occupied[0]
        for second in activities[index + 1 :]:
            second_footprint = footprints[second.activity_id]
            second_zone = closure_zone(second_footprint)
            second_occupied = set(second_footprint.occupied)
            second_anchor = second_footprint.occupied[0]
            shared = first_occupied & second_occupied
            intrudes = bool(second_occupied & first_zone) or bool(
                first_occupied & second_zone
            )

            if week_strict:
                if not intrudes:
                    continue
                for week in range(1, instance.horizon_weeks + 1):
                    booked = [
                        variables.access[first.activity_id, week],
                        variables.access[second.activity_id, week],
                    ]
                    if shared:
                        # They can only coexist that week as one possession,
                        # which rule 5 exempts from each other's closures.
                        model.add(
                            variables.possession[first.activity_id, week, first_anchor]
                            == variables.possession[
                                second.activity_id, week, second_anchor
                            ]
                        ).only_enforce_if(booked)
                    else:
                        # No shared location means no possible co-share, so the
                        # week cannot hold both at all.
                        model.add(sum(booked) <= 1)
                continue

            # Possession reading: separate possessions are separate nights, so
            # only a shared possession would place the pair on one night.
            if not intrudes and set(
                first_footprint.occupied
                + first_footprint.buffers
                + first_footprint.mirrored
                + first_footprint.cross_line
            ).isdisjoint(
                second_footprint.occupied
                + second_footprint.buffers
                + second_footprint.mirrored
                + second_footprint.cross_line
            ):
                continue
            # A common occupied location with the same group is an intentional
            # co-share; the possession module enforces its PM/PC/C legal mix.
            if shared:
                continue
            for week in range(1, instance.horizon_weeks + 1):
                model.add(
                    variables.possession[first.activity_id, week, first_anchor]
                    != variables.possession[second.activity_id, week, second_anchor]
                ).only_enforce_if(
                    [
                        variables.access[first.activity_id, week],
                        variables.access[second.activity_id, week],
                    ]
                )
