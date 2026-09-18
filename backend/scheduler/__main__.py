import argparse
import json
from pathlib import Path

from scheduler.exporter import export_files
from scheduler.loader import InputError, load_directory
from scheduler.results import summarize_schedule
from scheduler.solver import prepare, solve


def main():
    parser = argparse.ArgumentParser(
        description="Solve a railway track-access planning instance."
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--scenario", choices=["A", "B", "C"], default="A")
    parser.add_argument("--output", type=Path, help="Write the JSON solve report here.")
    parser.add_argument(
        "--submission-dir",
        type=Path,
        help="Write SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv and RESULTS.csv here.",
    )
    parser.add_argument("--time-limit", type=int, default=60)
    args = parser.parse_args()
    try:
        instance = load_directory(args.input_dir)
        report = prepare(instance, args.scenario)
        schedule = solve(instance, args.scenario, args.time_limit)
        report["solution"] = summarize_schedule(instance, schedule)
        report["notice"] = (
            "Solver output produced. Run the reference validator before operational use."
        )
    except (InputError, RuntimeError) as exc:
        parser.exit(1, "Input errors: " + str(exc) + "\n")

    if args.submission_dir:
        args.submission_dir.mkdir(parents=True, exist_ok=True)
        for name, content in export_files(instance, schedule, args.scenario).items():
            (args.submission_dir / name).write_bytes(content)
    content = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Solve report saved to {args.output}.")
    else:
        print(content)


if __name__ == "__main__":
    main()
