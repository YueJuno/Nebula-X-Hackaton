"""Calculate spatial footprints; does not enforce conflicts between jobs."""

from pydantic import BaseModel

from scheduler.domain import Activity, Instance, Location


class Footprint(BaseModel):
    activity_id: str
    occupied: list[str]
    buffers: list[str]
    mirrored: list[str]
    cross_line: list[str]
    affected_lines: list[str]


def calculate_footprint(instance: Instance, activity: Activity) -> Footprint:
    locations = {x.location_id: x for x in instance.locations}
    stations = {(x.line_code, x.station_id): x.seq for x in instance.stations}
    sectors = {x.sector_id: x for x in instance.sectors}
    start, end = (
        locations[activity.start_location_id],
        locations[activity.end_location_id],
    )
    line, bound = start.line_code, start.bound

    def extent(location: Location):
        if location.location_kind == "platform sector":
            seq = stations[(location.line_code, location.location_id.split(":")[2])]
            return seq, seq
        sector = sectors[location.location_id.rsplit(":", 1)[0]]
        return stations[(sector.line_code, sector.from_station_id)], stations[
            (sector.line_code, sector.to_station_id)
        ]

    lo = min(extent(start)[0], extent(end)[0])
    hi = max(extent(start)[1], extent(end)[1])

    def span(low, high):
        return {
            x.location_id
            for x in instance.locations
            if x.line_code == line
            and x.bound == bound
            and extent(x)[0] >= low
            and extent(x)[1] <= high
        }

    occupied = span(lo, hi)
    contract = instance.contract_for(activity)
    rule = next(
        x
        for x in instance.buffer_rules
        if x.nature_of_works == contract.nature_of_activity
    )
    closure = span(lo - rule.up_to_buffer_sectors, hi + rule.up_to_buffer_sectors)
    opposite = "WB" if bound == "EB" else "EB"
    mirrored = (
        {x.rsplit(":", 1)[0] + ":" + opposite for x in closure}
        if rule.opposite_bound_required
        else set()
    )
    cross_line = set()
    if contract.nature_of_activity == "Live":
        # The interchange crossover is triggered by a closure reaching its hubs/sector.
        touched = {x.split(":")[2] for x in closure | mirrored}
        if touched & {"H01", "H02", "H01_H02"}:
            cross_line = {
                x.location_id
                for x in instance.locations
                if x.line_code != line
                and x.location_id.split(":")[2] in {"H01", "H02", "H01_H02"}
            }
    affected = {line} | {locations[x].line_code for x in cross_line}
    return Footprint(
        activity_id=activity.activity_id,
        occupied=sorted(occupied),
        buffers=sorted(closure - occupied),
        mirrored=sorted(mirrored),
        cross_line=sorted(cross_line),
        affected_lines=sorted(affected),
    )


def calculate_footprints(instance: Instance) -> dict[str, Footprint]:
    return {
        a.activity_id: calculate_footprint(instance, a) for a in instance.activities
    }
