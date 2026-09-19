"""Legal possession mixes, co-sharing, capacity and excess accounting."""

from itertools import pairwise

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    location_by_id = {location.location_id: location for location in instance.locations}

    # Co-share labels are local to a location/week. An access may therefore use
    # different labels along its route, as shown by the reference submission.
    for activity in instance.activities:
        occupied = footprints[activity.activity_id].occupied
        for week in range(1, instance.horizon_weeks + 1):
            access = variables.access[activity.activity_id, week]
            for location_id in occupied:
                group_var = variables.possession[
                    activity.activity_id, week, location_id
                ]
                memberships = []
                for group in range(1, variables.max_groups + 1):
                    member = variables.in_group[
                        activity.activity_id, week, location_id, group
                    ]
                    memberships.append(member)
                    model.add(group_var == group).only_enforce_if(member)
                model.add(sum(memberships) == access)

    # Rule 5: one possession is one access-night. Two activities of the same
    # contract+type that share a possession therefore fall on the same granted
    # night, and two separate possessions at a location they share fall on
    # different ones. Only overlapping spans are comparable, because group
    # labels are local to a location/week.
    by_contract_type = {}
    for activity in instance.activities:
        by_contract_type.setdefault(
            (activity.contract_number, activity.activity_type), []
        ).append(activity)

    for activities in by_contract_type.values():
        for index, first in enumerate(activities):
            first_occupied = footprints[first.activity_id].occupied
            for second in activities[index + 1 :]:
                second_occupied = footprints[second.activity_id].occupied
                if set(first_occupied).isdisjoint(second_occupied):
                    continue
                for week in range(1, instance.horizon_weeks + 1):
                    together = model.new_bool_var(
                        f"same_possession_{first.activity_id}_{second.activity_id}_{week}"
                    )
                    first_group = variables.possession[
                        first.activity_id, week, first_occupied[0]
                    ]
                    second_group = variables.possession[
                        second.activity_id, week, second_occupied[0]
                    ]
                    model.add(first_group == second_group).only_enforce_if(together)
                    model.add(first_group != second_group).only_enforce_if(~together)
                    booked = [
                        variables.access[first.activity_id, week],
                        variables.access[second.activity_id, week],
                    ]
                    first_night = variables.night[first.activity_id, week]
                    second_night = variables.night[second.activity_id, week]
                    model.add(first_night == second_night).only_enforce_if(
                        [together, *booked]
                    )
                    model.add(first_night != second_night).only_enforce_if(
                        [~together, *booked]
                    )

    for location_id, location in location_by_id.items():
        candidates = [
            activity
            for activity in instance.activities
            if location_id in footprints[activity.activity_id].occupied
        ]
        for week in range(1, instance.horizon_weeks + 1):
            excess = variables.excess[location_id, week]
            if policy.max_excess_per_location_week is not None:
                model.add(excess <= policy.max_excess_per_location_week)

            used_groups = []
            for group in range(1, variables.max_groups + 1):
                members = [
                    variables.in_group[activity.activity_id, week, location_id, group]
                    for activity in candidates
                ]
                if not members:
                    continue
                used = model.new_bool_var(f"group_used_{location_id}_{week}_{group}")
                variables.group_used[location_id, week, group] = used
                model.add_max_equality(used, members)
                used_groups.append(used)

                pm_members = []
                pc_members = []
                for activity, member in zip(candidates, members, strict=True):
                    access_type = instance.contract_for(activity).access_type
                    if access_type == "PM":
                        pm_members.append(member)
                    elif access_type == "PC":
                        pc_members.append(member)

                total = sum(members)
                pm_count = sum(pm_members) if pm_members else 0
                pc_count = sum(pc_members) if pc_members else 0
                model.add(total <= 4)
                model.add(pc_count <= 1)
                # A PM is alone; otherwise PC+C or C-only may fill four spots.
                model.add(total + 3 * pm_count <= 4)

            # Labels are arbitrary. Requiring active labels to form a prefix
            # removes equivalent permutations without coupling other locations.
            for current, following in pairwise(used_groups):
                model.add(current >= following)

            model.add(excess >= sum(used_groups) - location.supply_capacity)
