import argparse
import json
from pathlib import Path

from scheduler.loader import InputError, load_directory
from scheduler.validator import validate_directory, validate_files


def main():
    parser = argparse.ArgumentParser(
        description="Solve or validate a railway track-access planning instance."
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--scenario", choices=["A", "B", "C"], default="A")
    parser.add_argument("--output", type=Path, help="Write the JSON report here.")
    parser.add_argument(
        "--submission-dir",
        type=Path,
        help="Write SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv and RESULTS.csv here.",
    )
    parser.add_argument(
        "--check",
        type=Path,
        metavar="SUBMISSION_DIR",
        help="Validate an existing submission against the instance and exit without solving.",
    )
    parser.add_argument(
        "--granularity",
        choices=["week", "possession"],
        default="week",
        help="How concurrency is read for buffers, when solving and when checking "
        "(see scheduler.rules). 'week' is the default because a week-strict "
        "schedule satisfies both readings.",
    )
    parser.add_argument("--time-limit", type=int, default=60)
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Add why-late diagnostics for every overrunning activity.",
    )
    parser.add_argument(
        "--unlocks",
        type=int,
        default=0,
        metavar="N",
        help="Re-solve the N most promising levers and rank them by objective bought back.",
    )
    args = parser.parse_args()

    try:
        instance = load_directory(args.input_dir)
        if args.check:
            report = validate_directory(instance, args.check, args.granularity)
        else:
            # Imported late so --check stays usable without the OR-Tools stack.
            from scheduler.exporter import export_files
            from scheduler.results import summarize_schedule
            from scheduler.solver import prepare, solve

            report = prepare(instance, args.scenario, args.granularity)
            schedule = solve(instance, args.scenario, args.time_limit, args.granularity)
            report["solution"] = summarize_schedule(instance, schedule)
            exports = export_files(instance, schedule, args.scenario)
            # Always self-check the export, so a solve never reports a schedule
            # the repository's own reading of the rules would reject.
            report["validation"] = validate_files(instance, exports, args.granularity)
            report["notice"] = "Solver output produced; see validation for feasibility."
            if args.explain or args.unlocks:
                from scheduler.explain import explain

                report["explanation"] = explain(
                    instance,
                    args.scenario,
                    schedule,
                    with_levers=bool(args.unlocks),
                    limit=args.unlocks or 6,
                    time_limit_seconds=max(10, args.time_limit // 2),
                )
            if args.submission_dir:
                args.submission_dir.mkdir(parents=True, exist_ok=True)
                for name, content in exports.items():
                    (args.submission_dir / name).write_bytes(content)
    except (InputError, RuntimeError) as exc:
        parser.exit(1, "Input errors: " + str(exc) + "\n")

    content = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Report saved to {args.output}.")
    else:
        print(content)

    if args.check:
        verdict = "FEASIBLE" if report["feasible"] else "INFEASIBLE"
        counts = report["detail"].get("violations_by_rule", {})
        summary = ", ".join(f"{rule}={count}" for rule, count in counts.items())
        print(f"\n{verdict} ({args.granularity} granularity){': ' + summary if summary else ''}")
        parser.exit(0 if report["feasible"] else 2)


if __name__ == "__main__":
    main()
