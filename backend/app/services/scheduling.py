"""Pure job workflow. SQL persistence is handled by the worker."""

from pathlib import Path
from tempfile import TemporaryDirectory

from scheduler.constraints import missing_constraints
from scheduler.domain import Instance
from scheduler.exporter import export_files, zip_files
from scheduler.results import summarize_schedule
from scheduler.solver import prepare, solve
from scheduler.validator import validate_submission


def execute_run(
    payload: dict,
    files: dict,
    scenario: str,
    validator_command=None,
    time_limit_seconds=60,
) -> dict:
    instance = Instance.model_validate(payload)
    report = prepare(instance, scenario)
    if missing_constraints():
        return {
            "status": "blocked",
            "message": "Preparation complete. Scheduling is blocked until railway constraints are implemented.",
            "report": report,
            "schedule": None,
            "submission_zip": None,
        }
    schedule = solve(instance, scenario, time_limit_seconds)
    exports = export_files(instance, schedule, scenario)
    report["solution"] = summarize_schedule(instance, schedule)
    with TemporaryDirectory(prefix="trackaccess-") as directory:
        inputs, outputs = Path(directory) / "instance", Path(directory) / "submission"
        inputs.mkdir()
        outputs.mkdir()
        for name, text in files.items():
            (inputs / name).write_text(text, encoding="utf-8")
        for name, content in exports.items():
            (outputs / name).write_bytes(content)
        validation = validate_submission(validator_command, inputs, outputs)
    report["notice"] = (
        "Solver output produced; see reference validation for feasibility."
    )
    report["validation"] = validation
    verified = (
        validation.get("status") == "validated" and validation.get("feasible") is True
    )
    return {
        "status": "completed" if verified else "needs_validation",
        "message": "Reference-validated schedule ready."
        if verified
        else "Solver output is ready for download but has not been checked by the reference validator.",
        "report": report,
        "schedule": schedule.model_dump(),
        "submission_zip": zip_files(exports),
    }
