import argparse
import json
from pathlib import Path

from scheduler.loader import InputError, load_directory
from scheduler.solver import prepare


def main():
    parser = argparse.ArgumentParser(
        description="Load data and prepare the scheduling model; constraints are pending."
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--scenario", choices=["A", "B", "C"], default="A")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = prepare(load_directory(args.input_dir), args.scenario)
    except InputError as exc:
        parser.exit(1, "Input errors: " + str(exc) + "\n")
    content = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Preparation report saved to {args.output}. No schedule generated.")
    else:
        print(content)


if __name__ == "__main__":
    main()
