"""Small non-public instances to catch assumptions tied to the supplied data."""

from datetime import date

import pytest

from scheduler.exporter import export_files
from scheduler.loader import load_files
from scheduler.solver import solve
from scheduler.validator import validate_files


def tiny_instance():
    locations = [
        f"PLAT:{line}:{station}:{bound},platform sector,{line},{bound},1"
        for line in ("ALP", "BET")
        for station in ("H01", "H02")
        for bound in ("EB", "WB")
    ] + [
        f"SEC:{line}:H01_H02:{bound},tunnel sector,{line},{bound},1"
        for line in ("ALP", "BET")
        for bound in ("EB", "WB")
    ]
    files = {
        "01_LINES.csv": "line_code,line_name\nALP,Alpha\nBET,Beta\n",
        "02_STATIONS.csv": (
            "station_id,line_code,seq,is_interchange\n"
            "H01,ALP,1,true\nH02,ALP,2,true\n"
            "H01,BET,1,true\nH02,BET,2,true\n"
        ),
        "03_SECTORS.csv": (
            "sector_id,line_code,from_station_id,to_station_id,seq,is_shared\n"
            "SEC:ALP:H01_H02,ALP,H01,H02,1,false\n"
            "SEC:BET:H01_H02,BET,H01,H02,1,false\n"
        ),
        "04_LOCATION_SUPPLY.csv": (
            "location_id,location_kind,line_code,bound,supply_capacity\n"
            + "\n".join(locations)
            + "\n"
        ),
        "05_BUFFER_LOCATION.csv": (
            "nature_of_works,up_to_buffer_sectors,opposite_bound_required\n"
            "Live,2,true\nNon-live (Consist),1,false\n"
            "Non-live (Others),0,false\n"
        ),
        "06_PARAMETERS.csv": "key,value\nhorizon_start,2027-01-04\nhorizon_weeks,3\n",
        "07_PROJECT_DETAILS.csv": (
            "contract_number,contract_description,contract_award_date,activity_type,"
            "nature_of_activity,contract_priority,contract_completion_date,"
            "planned_completion_date,number_of_workfronts,access_type,"
            "number_of_maximum_access_per_week\n"
            "C001,Test work,2026-01-01,Work,Non-live (Others),3,"
            "2027-02-28,2027-01-10,1,C,1\n"
        ),
        "08_ACTIVITY_DETAILS.csv": (
            "activity_id,contract_number,activity_type,start_location_id,"
            "end_location_id,total_accesses,planned_start_date,"
            "predecessor_activity_id,activity_priority\n"
            "A001,C001,Work,SEC:ALP:H01_H02:EB,SEC:ALP:H01_H02:EB,"
            "1,2027-01-06,,3\n"
        ),
    }
    return load_files({name: content.encode() for name, content in files.items()})


@pytest.mark.parametrize("scenario", ["A", "B", "C"])
def test_non_public_instance_with_midweek_start_schedules_and_validates(scenario):
    instance = tiny_instance()
    assert instance.activities[0].planned_start_date == date(2027, 1, 6)
    schedule = solve(instance, scenario, time_limit_seconds=5)
    assert [access.week for access in schedule.accesses] == [1]
    files = export_files(instance, schedule, scenario)
    for granularity in ("week", "possession"):
        report = validate_files(instance, files, granularity)
        assert report["feasible"], report["detail"]["violations_by_rule"]


@pytest.mark.parametrize("scenario", ["B", "C"])
def test_flexible_supply_can_buy_a_possession_at_zero_supply(scenario):
    instance = tiny_instance()
    occupied = {
        "PLAT:ALP:H01:EB",
        "SEC:ALP:H01_H02:EB",
        "PLAT:ALP:H02:EB",
    }
    for location in instance.locations:
        if location.location_id in occupied:
            location.supply_capacity = 0
    schedule = solve(instance, scenario, time_limit_seconds=5)
    report = validate_files(instance, export_files(instance, schedule, scenario))
    assert report["feasible"], report["detail"]["violations_by_rule"]
    assert report["soft_scores"]["excess_access_nights_total"] == 3
