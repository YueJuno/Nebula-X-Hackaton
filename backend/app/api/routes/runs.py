import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import current_user
from app.api.routes.instances import owned_dataset
from app.db.session import get_db
from app.models.scheduling import Run
from app.models.user import User
from app.schemas.scheduling import RunRequest, RunResponse
from scheduler.constraints import missing_constraints
from scheduler.loader import REQUIRED_FILES

router = APIRouter(prefix="/runs", tags=["scheduling runs"])
UserDependency = Annotated[User, Depends(current_user)]
DatabaseDependency = Annotated[Session, Depends(get_db)]


def owned_run(db, run_id, user_id):
    run = db.scalar(select(Run).where(Run.id == run_id, Run.owner_id == user_id))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@router.get("/capabilities")
def capabilities():
    missing = missing_constraints()
    return {
        "can_schedule": not missing,
        "can_prepare": True,
        "missing_constraints": missing,
        "required_files": REQUIRED_FILES,
    }


@router.post("", response_model=RunResponse, status_code=202)
def create_run(payload: RunRequest, user: UserDependency, db: DatabaseDependency):
    owned_dataset(db, payload.dataset_id, user.id)
    # Serialize the per-user quota check when several requests arrive together.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    active = db.scalars(
        select(Run.id).where(
            Run.owner_id == user.id, Run.status.in_(["queued", "running"])
        )
    ).all()
    if len(active) >= 3:
        raise HTTPException(
            status_code=429,
            detail="Wait for your existing runs to finish before starting another.",
        )
    run = Run(
        owner_id=user.id, dataset_id=payload.dataset_id, scenario=payload.scenario
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("", response_model=list[RunResponse])
def list_runs(user: UserDependency, db: DatabaseDependency):
    return db.scalars(
        select(Run)
        .where(Run.owner_id == user.id)
        .order_by(Run.created_at.desc())
        .limit(100)
    ).all()


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, user: UserDependency, db: DatabaseDependency):
    return owned_run(db, run_id, user.id)


@router.get("/{run_id}/report")
def download_report(run_id: str, user: UserDependency, db: DatabaseDependency):
    run = owned_run(db, run_id, user.id)
    if run.report is None:
        raise HTTPException(status_code=409, detail="Report is not ready.")
    return Response(
        json.dumps(run.report, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="report-{run.id}.json"'},
    )


@router.get("/{run_id}/submission")
def download_submission(run_id: str, user: UserDependency, db: DatabaseDependency):
    run = owned_run(db, run_id, user.id)
    if run.status != "completed" or not run.submission_zip:
        raise HTTPException(
            status_code=409, detail="No reference-validated submission is available."
        )
    return Response(
        run.submission_zip,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="scenario-{run.scenario}-{run.id}.zip"'
        },
    )
