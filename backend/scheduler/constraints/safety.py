"""Buffers, opposite-bound mirroring and interchange conflict rules.

The conservative week reading and the alternative possession reading are
kept separate. Co-share labels are local to each occupied location, so two
activities can only claim to share where their occupied spans overlap.
"""

IMPLEMENTED = True


def closure_zone(footprint):
    return (
        set(footprint.buffers) | set(footprint.mirrored) | set(footprint.cross_line)
    ) - set(footprint.occupied)


def add_constraints(model, variables, instance, footprints, policy):
    week_strict = policy.buffer_granularity == "week"
    activities = instance.activities

    for index, first in enumerate(activities):
        first_footprint = footprints[first.activity_id]
        first_occupied = set(first_footprint.occupied)
        first_zone = closure_zone(first_footprint)
        first_closure = first_occupied | first_zone

        for second in activities[index + 1 :]:
            second_footprint = footprints[second.activity_id]
            second_occupied = set(second_footprint.occupied)
            second_zone = closure_zone(second_footprint)
            shared_locations = sorted(first_occupied & second_occupied)
            intrudes = bool(
                second_occupied & first_zone
                or first_occupied & second_zone
                or first_zone & second_zone
            )

            if week_strict:
                if not intrudes:
                    continue
                for week in range(1, instance.horizon_weeks + 1):
                    booked = [
                        variables.access[first.activity_id, week],
                        variables.access[second.activity_id, week],
                    ]
                    if not shared_locations:
                        model.add(sum(booked) <= 1)
                        continue

                    # The pair can coexist only by co-sharing at an occupied
                    # location. A route-wide anchor is not a valid comparison.
                    same_local = []
                    for location_id in shared_locations:
                        same = model.new_bool_var(
                            f"safe_share_{first.activity_id}_{second.activity_id}"
                            f"_{week}_{location_id}"
                        )
                        first_group = variables.possession[
                            first.activity_id, week, location_id
                        ]
                        second_group = variables.possession[
                            second.activity_id, week, location_id
                        ]
                        model.add(first_group == second_group).only_enforce_if(same)
                        model.add(first_group != second_group).only_enforce_if(~same)
                        same_local.append(same)
                    model.add_bool_or(same_local).only_enforce_if(booked)
                continue

            # Under the possession reading, non-co-sharing possessions are on
            # different nights. Keep local closure slots distinct where two
            # disjoint occupied spans have overlapping closure footprints.
            if shared_locations:
                continue
            conflicting_locations = first_closure & (second_occupied | second_zone)
            if not conflicting_locations:
                continue
            for week in range(1, instance.horizon_weeks + 1):
                booked = [
                    variables.access[first.activity_id, week],
                    variables.access[second.activity_id, week],
                ]
                for location_id in conflicting_locations:
                    model.add(
                        variables.closure_group[first.activity_id, week, location_id]
                        != variables.closure_group[
                            second.activity_id, week, location_id
                        ]
                    ).only_enforce_if(booked)
