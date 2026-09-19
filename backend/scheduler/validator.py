"""Built-in reference validator, plus an adapter for an external one.

``validate`` implements PS1 section 2.4/2.5 directly and emits the section 2.7
report. It is the repository's own reading of the rules, not the official
scoring program, so a feasible verdict here is evidence, not proof.
"""

import json
import subprocess
from pathlib import Path

from scheduler.domain import Instance
from scheduler.loader import InputError
from scheduler.policies import get_policy
from scheduler.rules import (
    Granularity,
    Index,
    check_allocation,
    check_closures,
    check_eclo,
    check_planned_dates,
    check_possessions,
    check_predecessors,
    check_results,
    check_start_dates,
    check_structure,
    check_workload,
)
from scheduler.scoring import (
    FORMULA_VERSION,
    completion_table,
    objective_score,
    score_submission,
)
from scheduler.submission import (
    SUBMISSION_FILES,
    Submission,
    load_submission_directory,
    load_submission_files,
)
from scheduler.topology import calculate_footprints

MAX_REPORTED_VIOLATIONS = 200


def validate(
    instance: Instance,
    submission: Submission,
    granularity: Granularity = "week",
) -> dict:
    """Check one submission against its instance and return the section 2.7 report."""
    policy = get_policy(submission.scenario)
    index = Index.build(instance, submission, calculate_footprints(instance))
    completion = completion_table(index)

    violations = [
        *check_structure(index),
        *check_workload(index),
        *check_start_dates(index),
        *check_predecessors(index),
        *check_closures(index, granularity),
        *check_possessions(index, policy),
        *check_allocation(index),
        *check_eclo(index, policy),
        *check_planned_dates(policy, completion),
        *check_results(index, completion),
    ]
    soft_scores, detail = score_submission(index, policy, completion)
    feasible = not violations
    if feasible:
        soft_scores = {
            **soft_scores,
            "objective_score": objective_score(soft_scores, policy),
            "formula_version": FORMULA_VERSION,
        }

    counts: dict[str, int] = {}
    for violation in violations:
        counts[violation.rule] = counts.get(violation.rule, 0) + 1
    detail = {
        **detail,
        "closure_granularity": granularity,
        "hard_violations_total": len(violations),
        "violations_by_rule": dict(sorted(counts.items())),
        "contracts": sorted(completion.values(), key=lambda row: row["contract_number"]),
    }
    return {
        "scenario": submission.scenario,
        "feasible": feasible,
        "hard_violations": [
            violation.model_dump()
            for violation in violations[:MAX_REPORTED_VIOLATIONS]
        ],
        "soft_scores": soft_scores,
        "detail": detail,
        "status": "validated",
        "validator": "built-in",
    }


def unparseable(errors: list[str]) -> dict:
    """Section 2.7: soft scores stay empty only when the files fail to parse."""
    return {
        "scenario": None,
        "feasible": False,
        "hard_violations": [
            {"rule": "format", "severity": "hard", "detail": error}
            for error in errors[:MAX_REPORTED_VIOLATIONS]
        ],
        "soft_scores": {},
        "detail": {},
        "status": "validated",
        "validator": "built-in",
    }


def validate_files(
    instance: Instance,
    files: dict[str, bytes],
    granularity: Granularity = "week",
) -> dict:
    try:
        return validate(instance, load_submission_files(files), granularity)
    except InputError as exc:
        return unparseable(exc.errors)


def validate_directory(
    instance: Instance,
    directory: Path,
    granularity: Granularity = "week",
) -> dict:
    try:
        return validate(instance, load_submission_directory(directory), granularity)
    except InputError as exc:
        return unparseable(exc.errors)


def validate_submission(
    command: list[str] | None, instance_dir: Path, submission_dir: Path, timeout=60
) -> dict:
    """Adapter for the official scoring program, when one is configured."""
    if not command:
        return {
            "status": "unavailable",
            "feasible": None,
            "detail": "No external validator is configured. Set VALIDATOR_COMMAND to cross-check the built-in report.",
        }
    args = [
        arg.replace("{instance_dir}", str(instance_dir)).replace(
            "{submission_dir}", str(submission_dir)
        )
        for arg in command
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
        if len(result.stdout) > 2_000_000:
            raise ValueError("Validator output exceeds limit")
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or not isinstance(report.get("feasible"), bool):
            raise TypeError("Expected a JSON report with a boolean feasible field")
        if result.returncode != 0 and report["feasible"]:
            raise ValueError(
                "Validator exited unsuccessfully despite claiming feasibility"
            )
        return {**report, "status": "validated", "validator": "external"}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return {
            "status": "error",
            "feasible": None,
            "detail": "External validator failed or returned an invalid report.",
        }


__all__ = [
    "SUBMISSION_FILES",
    "validate",
    "validate_directory",
    "validate_files",
    "validate_submission",
]
