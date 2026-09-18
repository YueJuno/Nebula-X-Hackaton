"""Development worker with code reload, including Windows bind-mount polling."""

import os
from pathlib import Path

from watchfiles import run_process

from app.workers.scheduling import main

def start_dev_worker():
    backend = Path(__file__).resolve().parents[2]
    # run_process reads this setting through its underlying watcher; it has no
    # force_polling keyword argument of its own.
    os.environ.setdefault("WATCHFILES_FORCE_POLLING", "true")
    return run_process(backend / "app", backend / "scheduler", target=main)


if __name__ == "__main__":
    start_dev_worker()
