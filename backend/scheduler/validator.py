"""Optional external reference-validator adapter; never invents feasibility."""

import json
import subprocess
from pathlib import Path


def validate_submission(
    command: list[str] | None, instance_dir: Path, submission_dir: Path, timeout=60
) -> dict:
    if not command:
        return {
            "status": "unavailable",
            "feasible": None,
            "detail": "No reference validator is bundled. Configure VALIDATOR_COMMAND when it is available.",
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
        return {**report, "status": "validated"}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return {
            "status": "error",
            "feasible": None,
            "detail": "Reference validator failed or returned an invalid report.",
        }
