"""Hard-rule checks for PS1 section 2.4/2.5. Checks report breaches; they never raise.

Two readings of the buffer rule are defensible and the challenge pack ships no
reference binary to settle it, so the granularity is explicit:

* ``week``       - any two activities holding an access in the same week conflict
                   when one's occupied span falls inside the other's closure
                   or their closure zones overlap.
                   Matches the week-granular pinpoint in the section 2.7 example
                   ("wk4: A012 inside closure of ['A010'] ...") and is the safe
                   reading, because neither submitted field orders nights across
                   contracts: ``access_night`` is explicitly local to a
                   contract+type, and ``co_share_group`` is an arbitrary label.
* ``possession`` - only activities sharing a ``co_share_group`` label in that week
                   are treated as concurrent, taking rule 5's "separate
                   possessions on separate nights" as a network-wide guarantee.

Co-sharing (rule 5) exempts a pair under either reading.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel

from scheduler.domain import Instance
from scheduler.policies import Policy
from scheduler.submission import Submission
from scheduler.topology import Footprint

Granularity = Literal["week", "possession"]


class Violation(BaseModel):
    rule: str
    severity: str = "hard"
    detail: str


def show(locations, limit: int = 3) -> str:
    items = sorted(locations)
    text = ", ".join(f"'{item}'" for item in items[:limit])
    if len(items) > limit:
        text += f", +{len(items) - limit} more"
    return f"[{text}]"


def week_of(instance: Instance, day: date) -> int:
    return max(1, (day - instance.horizon_start).days // 7 + 1)


@dataclass
class Index:
    """Cross-referenced view of one submission against its instance."""

    instance: Instance
    submission: Submission
    footprints: dict[str, Footprint]
    known: set = field(default_factory=set)
    accesses: dict = field(default_factory=lambda: defaultdict(list))
    access_at: dict = field(default_factory=lambda: defaultdict(list))
    occupancy_at: dict = field(default_factory=lambda: defaultdict(list))
    groups_at: dict = field(default_factory=lambda: defaultdict(set))
    members: dict = field(default_factory=lambda: defaultdict(list))
    active: dict = field(default_factory=lambda: defaultdict(list))
    occupied: dict = field(default_factory=dict)
    zone: dict = field(default_factory=dict)

    @classmethod
    def build(cls, instance, submission, footprints):
        index = cls(instance=instance, submission=submission, footprints=footprints)
        index.known = {activity.activity_id for activity in instance.activities}
        for activity_id, footprint in footprints.items():
            index.occupied[activity_id] = set(footprint.occupied)
            # A closure zone is what the activity shuts without booking it.
            index.zone[activity_id] = (
                set(footprint.buffers)
                | set(footprint.mirrored)
                | set(footprint.cross_line)
            ) - set(footprint.occupied)
        for row in submission.accesses:
            if row.activity_id not in index.known:
                continue
            index.accesses[row.activity_id].append(row)
            index.access_at[row.activity_id, row.week].append(row)
            index.active[row.week].append(row.activity_id)
        for row in submission.occupancy:
            if row.activity_id not in index.known:
                continue
            index.occupancy_at[row.activity_id, row.week].append(row)
            index.groups_at[row.location_id, row.week].add(row.co_share_group)
            index.members[row.location_id, row.week, row.co_share_group].append(
                row.activity_id
            )
        for week, activity_ids in index.active.items():
            index.active[week] = sorted(set(activity_ids))
        return index

    def co_shared(self, first: str, second: str, week: int) -> bool:
        """True when both sit in one possession: a shared location under one label."""
        return bool(
            {
                (row.location_id, row.co_share_group)
                for row in self.occupancy_at[first, week]
            }
            & {
                (row.location_id, row.co_share_group)
                for row in self.occupancy_at[second, week]
            }
        )


def check_structure(index: Index) -> list[Violation]:
    violations = []
    instance, submission = index.instance, index.submission
    for label, rows in (
        ("SCHEDULE_ACCESS.csv", submission.accesses),
        ("SCHEDULE_OCCUPANCY.csv", submission.occupancy),
    ):
        for activity_id in sorted({row.activity_id for row in rows} - index.known):
            violations.append(
                Violation(
                    rule="format", detail=f"{label}: unknown activity {activity_id}"
                )
            )
    for activity in instance.activities:
        rows = index.accesses[activity.activity_id]
        if rows and sorted(row.access_seq for row in rows) != list(
            range(1, len(rows) + 1)
        ):
            violations.append(
                Violation(
                    rule="format",
                    detail=f"{activity.activity_id}: access_seq must run 1..{len(rows)}",
                )
            )
        if any(row.week > instance.horizon_weeks for row in rows):
            violations.append(
                Violation(
                    rule="format",
                    detail=f"{activity.activity_id}: access beyond week {instance.horizon_weeks}",
                )
            )
        for week in sorted({row.week for row in rows}):
            if len(index.access_at[activity.activity_id, week]) > 1:
                violations.append(
                    Violation(
                        rule="allocation",
                        detail=f"wk{week}: {activity.activity_id} holds more than one access-night",
                    )
                )
    for (activity_id, week), rows in sorted(index.occupancy_at.items()):
        if not index.access_at[activity_id, week]:
            violations.append(
                Violation(
                    rule="occupancy",
                    detail=f"wk{week}: {activity_id} occupies locations without an access row",
                )
            )
    for (activity_id, week), _rows in sorted(index.access_at.items()):
        booked = {row.location_id for row in index.occupancy_at[activity_id, week]}
        required = index.occupied[activity_id]
        if missing := required - booked:
            violations.append(
                Violation(
                    rule="occupancy",
                    detail=f"wk{week}: {activity_id} does not book its full span; "
                    f"missing {show(missing)}",
                )
            )
        if extra := booked - required:
            violations.append(
                Violation(
                    rule="occupancy",
                    detail=f"wk{week}: {activity_id} books outside its span at {show(extra)}",
                )
            )
    return violations


def check_workload(index: Index) -> list[Violation]:
    """Rule 1: every activity delivered in full; a standard night is 1.0, ECLO 1.5."""
    violations = []
    for activity in index.instance.activities:
        rows = index.accesses[activity.activity_id]
        if not rows:
            violations.append(
                Violation(
                    rule="workload",
                    detail=f"{activity.activity_id} is not scheduled; "
                    "every activity must be delivered in full",
                )
            )
            continue
        # Count in halves so the 1.5 ECLO yield stays exact.
        delivered = sum(3 if row.eclo else 2 for row in rows)
        if delivered < 2 * activity.total_accesses:
            violations.append(
                Violation(
                    rule="workload",
                    detail=f"{activity.activity_id} delivers {delivered / 2:g} of "
                    f"{activity.total_accesses} required accesses",
                )
            )
    return violations


def check_start_dates(index: Index) -> list[Violation]:
    """Rule 2: no activity starts before its planned start week."""
    violations = []
    for activity in index.instance.activities:
        earliest = week_of(index.instance, activity.planned_start_date)
        for row in sorted(index.accesses[activity.activity_id], key=lambda r: r.week):
            if row.week < earliest:
                violations.append(
                    Violation(
                        rule="start_date",
                        detail=f"wk{row.week}: {activity.activity_id} starts before its "
                        f"planned start week {earliest} ({activity.planned_start_date})",
                    )
                )
    return violations


def check_predecessors(index: Index) -> list[Violation]:
    """Not enumerated in section 2.4, but the instance models the dependency."""
    violations = []
    for activity in index.instance.activities:
        predecessor = activity.predecessor_activity_id
        if not predecessor or predecessor not in index.known:
            continue
        before, after = (
            index.accesses[predecessor],
            index.accesses[activity.activity_id],
        )
        if (
            before
            and after
            and max(r.week for r in before) >= min(r.week for r in after)
        ):
            violations.append(
                Violation(
                    rule="predecessor",
                    detail=f"{activity.activity_id} starts in wk{min(r.week for r in after)} "
                    f"before {predecessor} finishes in wk{max(r.week for r in before)}",
                )
            )
    return violations


def check_closures(index: Index, granularity: Granularity) -> list[Violation]:
    """Rule 3: buffers, opposite-bound mirroring and the Live interchange crossover."""
    violations = []
    for week in sorted(index.active):
        active = index.active[week]
        for offender in active:
            zone = index.zone[offender]
            if not zone:
                continue
            for victim in active:
                if victim == offender:
                    continue
                hit = index.occupied[victim] & zone
                if not hit or index.co_shared(offender, victim, week):
                    continue
                # Labels are local to a location, not a network-wide night ID.
                # Under the possession reading, non-co-sharing pairs are on
                # separate nights and their labels cannot be compared here.
                if granularity == "possession":
                    continue
                violations.append(
                    Violation(
                        rule="closure",
                        detail=f"wk{week}: {victim} inside closure of "
                        f"['{offender}'] at {show(hit)}",
                    )
                )
        if granularity == "week":
            for position, first in enumerate(active):
                for second in active[position + 1 :]:
                    overlap = index.zone[first] & index.zone[second]
                    if not overlap or index.co_shared(first, second, week):
                        continue
                    # An occupied/closure collision was already reported for
                    # this pair. Only add an otherwise-missed buffer overlap.
                    if (
                        index.occupied[first] & index.zone[second]
                        or index.occupied[second] & index.zone[first]
                    ):
                        continue
                    violations.append(
                        Violation(
                            rule="closure",
                            detail=f"wk{week}: closure zones of {first} and "
                            f"{second} overlap at {show(overlap)}",
                        )
                    )
    return violations


def check_possessions(index: Index, policy: Policy) -> list[Violation]:
    """Rules 4 and 5: legal mixes per possession, and capacity per location-week."""
    violations = []
    instance = index.instance
    activities = {item.activity_id: item for item in instance.activities}

    for (location_id, week, group), member_ids in sorted(index.members.items()):
        members = [activities[a] for a in member_ids if a in activities]
        types = [instance.contract_for(item).access_type for item in members]
        where = f"wk{week} {location_id} possession {group}"
        if len(members) > 4:
            violations.append(
                Violation(
                    rule="mix",
                    detail=f"{where}: {len(members)} activities exceed the "
                    "4-per-possession capacity",
                )
            )
        if types.count("PM") and len(types) > 1:
            violations.append(
                Violation(
                    rule="mix",
                    detail=f"{where}: a PM must hold the possession alone, "
                    f"found {sorted(member_ids)}",
                )
            )
        if types.count("PC") > 1:
            violations.append(
                Violation(
                    rule="mix",
                    detail=f"{where}: {types.count('PC')} PC possession masters; "
                    "at most one is legal",
                )
            )
    allowance = policy.max_excess_per_location_week
    if allowance is None:
        return violations
    for location in sorted(instance.locations, key=lambda item: item.location_id):
        for week in range(1, instance.horizon_weeks + 1):
            used = len(index.groups_at[location.location_id, week])
            if used - location.supply_capacity > allowance:
                violations.append(
                    Violation(
                        rule="capacity",
                        detail=f"wk{week} {location.location_id}: {used} possessions "
                        f"against a supply of {location.supply_capacity}"
                        + (f" plus a {allowance} allowance" if allowance else ""),
                    )
                )
    return violations


def check_allocation(index: Index) -> list[Violation]:
    """Rules 6 and 7: weekly access-night budget and concurrent workfronts."""
    violations = []
    instance = index.instance
    activities = {item.activity_id: item for item in instance.activities}
    nights, fronts = defaultdict(set), defaultdict(set)
    for activity_id, rows in index.accesses.items():
        activity = activities[activity_id]
        key = activity.contract_number, activity.activity_type
        for row in rows:
            nights[key + (row.week,)].add(row.access_night)
            fronts[key + (row.week, row.access_night)].add(activity_id)

    contracts = {
        (item.contract_number, item.activity_type): item for item in instance.contracts
    }
    for (contract_number, activity_type, week), values in sorted(nights.items()):
        contract = contracts[contract_number, activity_type]
        granted = contract.number_of_maximum_access_per_week
        if len(values) > granted:
            violations.append(
                Violation(
                    rule="allocation",
                    detail=f"wk{week}: {contract_number}/{activity_type} uses "
                    f"{len(values)} access-nights against a weekly grant of {granted}",
                )
            )
        if beyond := sorted(value for value in values if value > granted):
            violations.append(
                Violation(
                    rule="allocation",
                    detail=f"wk{week}: {contract_number}/{activity_type} reports "
                    f"access_night {beyond} outside its 1..{granted} grant",
                )
            )

    for (contract_number, activity_type, week, night), members in sorted(
        fronts.items()
    ):
        contract = contracts[contract_number, activity_type]
        if len(members) > contract.number_of_workfronts:
            violations.append(
                Violation(
                    rule="workfront",
                    detail=f"wk{week} night {night}: {contract_number}/{activity_type} "
                    f"runs {len(members)} concurrent activities against "
                    f"{contract.number_of_workfronts} workfronts",
                )
            )
    return violations


def check_eclo(index: Index, policy: Policy) -> list[Violation]:
    """Rules 8 and 9: the Scenario A prohibition and Scenario C's per-line window."""
    violations = []
    if not policy.allow_eclo:
        for activity_id in sorted(index.accesses):
            for row in sorted(
                (r for r in index.accesses[activity_id] if r.eclo),
                key=lambda r: r.week,
            ):
                violations.append(
                    Violation(
                        rule="eclo",
                        detail=f"wk{row.week}: {activity_id} uses ECLO, which Scenario "
                        f"{policy.scenario} forbids outright",
                    )
                )
        return violations
    if not policy.eclo_window_weeks:
        return violations
    # A cross-line Live activity has to sit inside both lines' windows at once,
    # which falls out of charging its ECLO weeks to every line it affects.
    by_line = defaultdict(set)
    for activity_id, rows in index.accesses.items():
        for row in rows:
            if row.eclo:
                for line in index.footprints[activity_id].affected_lines:
                    by_line[line].add(row.week)
    for line, weeks in sorted(by_line.items()):
        span = max(weeks) - min(weeks) + 1
        if span > policy.eclo_window_weeks:
            violations.append(
                Violation(
                    rule="eclo_window",
                    detail=f"line {line}: ECLO nights span weeks {min(weeks)}-{max(weeks)} "
                    f"({span} weeks) against a continuous window of "
                    f"{policy.eclo_window_weeks}",
                )
            )
    return violations


def check_planned_dates(policy: Policy, completion: dict) -> list[Violation]:
    """Scenario B fixes the planned completion dates, so any overrun is a hard breach."""
    if not policy.fixed_deadlines:
        return []
    return [
        Violation(
            rule="planned_date",
            detail=f"{row['contract_number']} completes "
            f"{row['simulated_completion_date']} past its planned "
            f"{row['planned_completion_date']} ({row['overrun_days']} days), "
            f"which Scenario {policy.scenario} fixes",
        )
        for row in sorted(completion.values(), key=lambda r: r["contract_number"])
        if row["overrun_days"] > 0
    ]


def check_results(index: Index, completion: dict) -> list[Violation]:
    """RESULTS.csv must agree with the schedule it claims to summarise."""
    violations = []
    reported = {row.contract_number: row for row in index.submission.results}
    expected = set(completion)
    if missing := expected - set(reported):
        violations.append(
            Violation(
                rule="results",
                detail=f"RESULTS.csv omits contracts {', '.join(sorted(missing))}",
            )
        )
    if extra := set(reported) - expected:
        violations.append(
            Violation(
                rule="results",
                detail=f"RESULTS.csv reports unknown contracts {', '.join(sorted(extra))}",
            )
        )
    for contract_number in sorted(expected & set(reported)):
        row, actual = reported[contract_number], completion[contract_number]
        if (
            row.simulated_completion_date.isoformat()
            != actual["simulated_completion_date"]
        ):
            violations.append(
                Violation(
                    rule="results",
                    detail=f"{contract_number}: RESULTS.csv claims completion "
                    f"{row.simulated_completion_date}, schedule gives "
                    f"{actual['simulated_completion_date']}",
                )
            )
        if row.overrun_days != actual["overrun_days"]:
            violations.append(
                Violation(
                    rule="results",
                    detail=f"{contract_number}: RESULTS.csv claims {row.overrun_days} "
                    f"overrun days, schedule gives {actual['overrun_days']}",
                )
            )
    return violations
