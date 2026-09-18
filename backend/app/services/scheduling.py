"""Pure job workflow. SQL persistence is handled by the worker."""

from pathlib import Path
from tempfile import TemporaryDirectory

from scheduler.constraints import missing_constraints
from scheduler.domain import Instance
from scheduler.explain import explain
from scheduler.exporter import export_files, zip_files
from scheduler.results import summarize_schedule
from scheduler.solver import prepare, solve
from scheduler.validator import validate_files, validate_submission


def execute_run(
    payload: dict,
    files: dict,
    scenario: str,
    validator_command=None,
    time_limit_seconds=60,
    granularity="week",
) -> dict:
    instance = Instance.model_validate(payload)
    report = prepare(instance, scenario, granularity)
    if missing_constraints():
        return {
            "status": "blocked",
            "message": "Preparation complete. Scheduling is blocked until railway constraints are implemented.",
            "report": report,
            "schedule": None,
            "submission_zip": None,
        }
    schedule = solve(instance, scenario, time_limit_seconds, granularity)
    exports = export_files(instance, schedule, scenario)
    report["solution"] = summarize_schedule(instance, schedule)

    # Every run is checked against the repository's own reading of section 2.4
    # before it is offered for download.
    validation = validate_files(instance, exports, granularity)
    report["validation"] = validation
    # Why-late attribution reads the solved schedule only, so it is cheap enough
    # to run here; the lever sweep re-solves and stays in the CLI.
    report["explanation"] = explain(instance, scenario, schedule)

    external = {"status": "unavailable", "feasible": None}
    if validator_command:
        with TemporaryDirectory(prefix="trackaccess-") as directory:
            inputs = Path(directory) / "instance"
            outputs = Path(directory) / "submission"
            inputs.mkdir()
            outputs.mkdir()
            for name, text in files.items():
                (inputs / name).write_text(text, encoding="utf-8")
            for name, content in exports.items():
                (outputs / name).write_bytes(content)
            external = validate_submission(validator_command, inputs, outputs)
        report["external_validation"] = external

    feasible = validation.get("feasible") is True
    contradicted = external.get("feasible") is False
    verified = feasible and not contradicted
    if not feasible:
        counts = validation.get("detail", {}).get("violations_by_rule", {})
        message = "Schedule breaches " + ", ".join(
            f"{rule} ({count})" for rule, count in sorted(counts.items())
        ) + ". Download the CSVs to inspect the pinpoints."
    elif contradicted:
        message = "The built-in validator passed this schedule but the external validator rejected it."
    else:
        message = (
            f"Feasible under the built-in validator; objective "
            f"{validation['soft_scores'].get('objective_score')}."
            if external.get("feasible") is None
            else "Feasible under both the built-in and external validators."
        )
    report["notice"] = message
    return {
        "status": "completed" if verified else "needs_validation",
        "message": message,
        "report": report,
        "schedule": schedule.model_dump(),
        "submission_zip": zip_files(exports),
    }
