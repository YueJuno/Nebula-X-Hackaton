"""Legal possession mixes, co-sharing, capacity and excess accounting."""

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    location_by_id = {
        location.location_id: location for location in instance.locations
    }

    # One access is one possession, so use one stable group label across its
    # complete occupied span. Group labels remain local to each location/week
    # for capacity accounting and may be reused by spatially separate work.
    for activity in instance.activities:
        occupied = footprints[activity.activity_id].occupied
        for week in range(1, instance.horizon_weeks + 1):
            access = variables.access[activity.activity_id, week]
            anchor = variables.possession[
                activity.activity_id, week, occupied[0]
            ]
            for location_id in occupied:
                group_var = variables.possession[
                    activity.activity_id, week, location_id
                ]
                model.add(group_var == anchor)
                memberships = []
                for group in range(1, variables.max_groups + 1):
                    member = variables.in_group[
                        activity.activity_id, week, location_id, group
                    ]
                    memberships.append(member)
                    model.add(group_var == group).only_enforce_if(member)
                model.add(sum(memberships) == access)

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
                    variables.in_group[
                        activity.activity_id, week, location_id, group
                    ]
                    for activity in candidates
                ]
                if not members:
                    continue
                used = model.new_bool_var(
                    f"group_used_{location_id}_{week}_{group}"
                )
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

            model.add(
                excess >= sum(used_groups) - location.supply_capacity
            )
