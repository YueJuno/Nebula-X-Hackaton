"""Development worker with code reload, including Windows bind-mount polling."""

from pathlib import Path

from watchfiles import run_process

from app.workers.scheduling import main

if __name__ == "__main__":
    backend = Path(__file__).resolve().parents[2]
    run_process(backend / "app", backend / "scheduler", target=main, force_polling=True)
