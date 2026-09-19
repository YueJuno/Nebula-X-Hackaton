from datetime import date, timedelta
from types import SimpleNamespace

from ortools.sat.python import cp_model

from scheduler.constraints import possessions, safety, workload


def test_planned_start_allows_containing_week_but_blocks_prior_week():
    horizon_start = date(2027, 1, 4)  # Monday

    def solve_for(planned_start, selected_week):
        model = cp_model.CpModel()
        activity = SimpleNamespace(
            activity_id="A1",
            total_accesses=1,
            planned_start_date=planned_start,
            predecessor_activity_id="",
        )
        instance = SimpleNamespace(
            activities=[activity],
            horizon_weeks=2,
            week_end=lambda week: horizon_start + timedelta(days=7 * week - 1),
        )
        variables = SimpleNamespace(
            access={
                ("A1", week): model.new_bool_var(f"access_{week}") for week in (1, 2)
            },
            eclo={("A1", week): model.new_bool_var(f"eclo_{week}") for week in (1, 2)},
        )
        workload.add_constraints(model, variables, instance, {}, None)
        for week in (1, 2):
            model.add(variables.access["A1", week] == (week == selected_week))
            model.add(variables.eclo["A1", week] == 0)
        return cp_model.CpSolver().solve(model)

    assert solve_for(date(2027, 1, 6), 1) == cp_model.OPTIMAL
    assert solve_for(date(2027, 1, 13), 1) == cp_model.INFEASIBLE
    assert solve_for(date(2027, 1, 13), 2) == cp_model.OPTIMAL


def test_one_access_can_use_different_groups_at_different_locations():
    model = cp_model.CpModel()
    activities = [
        SimpleNamespace(activity_id="A1", contract_number="C1", activity_type="T1"),
        SimpleNamespace(activity_id="A2", contract_number="C2", activity_type="T2"),
    ]
    contracts = {
        "A1": SimpleNamespace(access_type="C"),
        "A2": SimpleNamespace(access_type="PM"),
    }
    locations = [
        SimpleNamespace(location_id="L1", supply_capacity=2),
        SimpleNamespace(location_id="L2", supply_capacity=2),
    ]
    instance = SimpleNamespace(
        activities=activities,
        locations=locations,
        horizon_weeks=1,
        contract_for=lambda activity: contracts[activity.activity_id],
    )
    footprints = {
        "A1": SimpleNamespace(occupied=["L1", "L2"]),
        "A2": SimpleNamespace(occupied=["L2"]),
    }
    possession = {
        ("A1", 1, "L1"): model.new_int_var(1, 2, "group_a1_l1"),
        ("A1", 1, "L2"): model.new_int_var(1, 2, "group_a1_l2"),
        ("A2", 1, "L2"): model.new_int_var(1, 2, "group_a2_l2"),
    }
    variables = SimpleNamespace(
        max_groups=2,
        access={
            (activity.activity_id, 1): model.new_bool_var(
                f"access_{activity.activity_id}"
            )
            for activity in activities
        },
        possession=possession,
        in_group={
            (activity_id, 1, location, group): model.new_bool_var(
                f"member_{activity_id}_{location}_{group}"
            )
            for activity_id, _week, location in possession
            for group in (1, 2)
        },
        group_used={},
        excess={
            ("L1", 1): model.new_int_var(0, 2, "excess_l1"),
            ("L2", 1): model.new_int_var(0, 2, "excess_l2"),
        },
    )
    policy = SimpleNamespace(max_excess_per_location_week=0)

    possessions.add_constraints(model, variables, instance, footprints, policy)
    model.add(variables.access["A1", 1] == 1)
    model.add(variables.access["A2", 1] == 1)
    model.add(variables.possession["A1", 1, "L1"] == 1)
    model.add(variables.possession["A2", 1, "L2"] == 1)

    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert solver.value(variables.possession["A1", 1, "L1"]) == 1
    assert solver.value(variables.possession["A1", 1, "L2"]) == 2


def test_buffer_conflict_uses_the_group_at_the_conflicting_location():
    model = cp_model.CpModel()
    activities = [
        SimpleNamespace(activity_id="A1"),
        SimpleNamespace(activity_id="A2"),
    ]
    instance = SimpleNamespace(activities=activities, horizon_weeks=1)
    footprints = {
        "A1": SimpleNamespace(
            occupied=["L1"], buffers=["L2"], mirrored=[], cross_line=[]
        ),
        "A2": SimpleNamespace(occupied=["L2"], buffers=[], mirrored=[], cross_line=[]),
    }
    variables = SimpleNamespace(
        access={
            ("A1", 1): model.new_bool_var("access_a1"),
            ("A2", 1): model.new_bool_var("access_a2"),
        },
        closure_group={
            ("A1", 1, "L2"): model.new_int_var(1, 2, "a1_at_l2"),
            ("A2", 1, "L2"): model.new_int_var(1, 2, "a2_at_l2"),
        },
    )

    safety.add_constraints(
        model,
        variables,
        instance,
        footprints,
        SimpleNamespace(buffer_granularity="possession"),
    )
    model.add(variables.access["A1", 1] == 1)
    model.add(variables.access["A2", 1] == 1)
    model.add(
        variables.closure_group["A1", 1, "L2"] == variables.closure_group["A2", 1, "L2"]
    )

    assert cp_model.CpSolver().solve(model) == cp_model.INFEASIBLE


def test_week_strict_rejects_overlapping_buffers_without_worksite_intrusion():
    model = cp_model.CpModel()
    activities = [SimpleNamespace(activity_id="A1"), SimpleNamespace(activity_id="A2")]
    instance = SimpleNamespace(activities=activities, horizon_weeks=1)
    footprints = {
        "A1": SimpleNamespace(
            occupied=["L1"], buffers=["L2"], mirrored=[], cross_line=[]
        ),
        "A2": SimpleNamespace(
            occupied=["L3"], buffers=["L2"], mirrored=[], cross_line=[]
        ),
    }
    variables = SimpleNamespace(
        access={
            ("A1", 1): model.new_bool_var("access_a1"),
            ("A2", 1): model.new_bool_var("access_a2"),
        }
    )
    safety.add_constraints(
        model,
        variables,
        instance,
        footprints,
        SimpleNamespace(buffer_granularity="week"),
    )
    model.add(variables.access["A1", 1] == 1)
    model.add(variables.access["A2", 1] == 1)

    assert cp_model.CpSolver().solve(model) == cp_model.INFEASIBLE


def test_same_location_and_group_is_a_co_share_exemption():
    model = cp_model.CpModel()
    activities = [
        SimpleNamespace(activity_id="A1"),
        SimpleNamespace(activity_id="A2"),
    ]
    instance = SimpleNamespace(activities=activities, horizon_weeks=1)
    footprints = {
        activity.activity_id: SimpleNamespace(
            occupied=["L1"], buffers=[], mirrored=[], cross_line=[]
        )
        for activity in activities
    }
    variables = SimpleNamespace(
        access={
            ("A1", 1): model.new_bool_var("access_a1"),
            ("A2", 1): model.new_bool_var("access_a2"),
        },
        closure_group={
            ("A1", 1, "L1"): model.new_int_var(1, 2, "a1_at_l1"),
            ("A2", 1, "L1"): model.new_int_var(1, 2, "a2_at_l1"),
        },
    )

    safety.add_constraints(
        model,
        variables,
        instance,
        footprints,
        SimpleNamespace(buffer_granularity="possession"),
    )
    model.add(variables.access["A1", 1] == 1)
    model.add(variables.access["A2", 1] == 1)
    model.add(
        variables.closure_group["A1", 1, "L1"] == variables.closure_group["A2", 1, "L1"]
    )

    assert cp_model.CpSolver().solve(model) == cp_model.OPTIMAL


def test_week_buffer_exemption_compares_a_shared_location_not_route_anchors():
    model = cp_model.CpModel()
    activities = [
        SimpleNamespace(activity_id="A1"),
        SimpleNamespace(activity_id="A2"),
    ]
    instance = SimpleNamespace(activities=activities, horizon_weeks=1)
    footprints = {
        "A1": SimpleNamespace(
            occupied=["L1", "L2"], buffers=["L3"], mirrored=[], cross_line=[]
        ),
        "A2": SimpleNamespace(
            occupied=["L2", "L3"], buffers=[], mirrored=[], cross_line=[]
        ),
    }
    variables = SimpleNamespace(
        access={
            ("A1", 1): model.new_bool_var("access_a1"),
            ("A2", 1): model.new_bool_var("access_a2"),
        },
        possession={
            (activity_id, 1, location): model.new_int_var(
                1, 2, f"group_{activity_id}_{location}"
            )
            for activity_id, footprint in footprints.items()
            for location in footprint.occupied
        },
    )
    safety.add_constraints(
        model,
        variables,
        instance,
        footprints,
        SimpleNamespace(buffer_granularity="week"),
    )
    model.add(variables.access["A1", 1] == 1)
    model.add(variables.access["A2", 1] == 1)
    model.add(variables.possession["A1", 1, "L1"] == 1)
    model.add(variables.possession["A1", 1, "L2"] == 2)
    model.add(variables.possession["A2", 1, "L2"] == 2)

    assert cp_model.CpSolver().solve(model) == cp_model.OPTIMAL
