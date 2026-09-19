"""PostgreSQL-backed queue: run with python -m app.workers.scheduling."""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.models.scheduling import Dataset, Run
from app.models.user import User  # noqa: F401 -- registers FK target in Base.metadata
from app.services.scheduling import execute_run

logger = logging.getLogger(__name__)


def process_next(engine, validator_command=None, time_limit_seconds=60) -> bool:
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        # Jobs exceeding their solve + validation allowance are recoverable on restart.
        db.execute(
            update(Run)
            .where(
                Run.status == "running",
                Run.started_at < now - timedelta(seconds=time_limit_seconds + 300),
            )
            .values(
                status="failed",
                message="Worker interrupted or exceeded its execution allowance.",
                finished_at=now,
            )
        )
        run = db.scalar(
            select(Run)
            .where(Run.status == "queued")
            .order_by(Run.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            return False
        run.status, run.started_at = "running", now
        dataset = db.get(Dataset, run.dataset_id)
        run_id, payload, files, scenario = (
            run.id,
            dataset.payload,
            dataset.files,
            run.scenario,
        )
    try:
        result = execute_run(
            payload, files, scenario, validator_command, time_limit_seconds
        )
    except Exception:  # noqa: BLE001 -- job boundary must persist unexpected failures too
        # Avoid writing uploaded data or connection credentials into user-facing errors.
        logger.error("Run %s failed during scheduling preparation or execution", run_id)
        result = {
            "status": "failed",
            "message": "Run failed during model preparation or solver execution.",
            "report": None,
            "schedule": None,
            "submission_zip": None,
        }
    with Session(engine) as db, db.begin():
        db.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == "running")
            .values(**result, finished_at=datetime.now(UTC))
        )
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    logger.info("Scheduling worker started")
    while True:
        try:
            if not process_next(
                get_engine(),
                settings.validator_command,
                settings.solver_time_limit_seconds,
            ):
                time.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception:  # noqa: BLE001 -- keep the worker alive across queue outages
            logger.exception("Worker cannot access or process the job queue")
            time.sleep(5)


if __name__ == "__main__":
    main()
