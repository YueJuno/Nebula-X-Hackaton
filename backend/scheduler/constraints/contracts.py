"""Weekly allocation, workfront, completion and lateness accounting."""

IMPLEMENTED = True


def add_constraints(model, variables, instance, footprints, policy):
    by_contract_type = {}
    for activity in instance.activities:
        by_contract_type.setdefault(
            (activity.contract_number, activity.activity_type), []
        ).append(activity)

    for activity in instance.activities:
        contract = instance.contract_for(activity)
        completion = variables.completion_week[activity.activity_id]
        model.add_max_equality(
            completion,
            [
                week * variables.access[activity.activity_id, week]
                for week in range(1, instance.horizon_weeks + 1)
            ],
        )

        deadline_offset = (
            instance.horizon_start - contract.planned_completion_date
        ).days - 1
        model.add_max_equality(
            variables.lateness[activity.activity_id],
            [0, 7 * completion + deadline_offset],
        )

        for week in range(1, instance.horizon_weeks + 1):
            access = variables.access[activity.activity_id, week]
            memberships = []
            for night in range(
                1, contract.number_of_maximum_access_per_week + 1
            ):
                member = variables.on_night[
                    activity.activity_id, week, night
                ]
                memberships.append(member)
                model.add(
                    variables.night[activity.activity_id, week] == night
                ).only_enforce_if(member)
            model.add(sum(memberships) == access)

            if (
                policy.fixed_deadlines
                and instance.week_end(week) > contract.planned_completion_date
            ):
                model.add(access == 0)

    for activities in by_contract_type.values():
        contract = instance.contract_for(activities[0])
        for week in range(1, instance.horizon_weeks + 1):
            for night in range(
                1, contract.number_of_maximum_access_per_week + 1
            ):
                model.add(
                    sum(
                        variables.on_night[
                            activity.activity_id, week, night
                        ]
                        for activity in activities
                    )
                    <= contract.number_of_workfronts
                )
