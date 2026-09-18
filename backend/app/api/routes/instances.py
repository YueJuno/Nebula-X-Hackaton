from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import current_user
from app.db.session import get_db
from app.models.scheduling import Dataset
from app.models.user import User
from app.schemas.scheduling import DatasetResponse
from scheduler.loader import REQUIRED_FILES, InputError, load_files

router = APIRouter(prefix="/instances", tags=["instances"])
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ACTIVITIES = 1000
MAX_LOCATIONS = 1000
UserDependency = Annotated[User, Depends(current_user)]
DatabaseDependency = Annotated[Session, Depends(get_db)]


def owned_dataset(db: Session, dataset_id: str, user_id: str) -> Dataset:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user_id)
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


@router.post("", response_model=DatasetResponse, status_code=201)
async def upload_instance(
    files: Annotated[list[UploadFile], File()],
    user: UserDependency,
    db: DatabaseDependency,
    name: Annotated[str, Form(min_length=1, max_length=128)] = "Uploaded instance",
):
    try:
        if len(files) != len(REQUIRED_FILES):
            raise HTTPException(
                status_code=422, detail="Upload exactly the eight instance CSV files."
            )
        contents = {}
        for file in files:
            if file.filename not in REQUIRED_FILES or file.filename in contents:
                raise HTTPException(
                    status_code=422, detail="Unexpected or duplicate CSV filename."
                )
            content = await file.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413, detail="Each CSV must be at most 2 MB."
                )
            contents[file.filename] = content
        try:
            instance = load_files(contents)
        except InputError as exc:
            raise HTTPException(status_code=422, detail={"errors": exc.errors[:100]})
        if (
            len(instance.activities) > MAX_ACTIVITIES
            or len(instance.locations) > MAX_LOCATIONS
        ):
            raise HTTPException(
                status_code=413,
                detail="Instance exceeds the current 1,000 activity/location upload limit.",
            )
        if (
            len(instance.activities) * len(instance.locations) * instance.horizon_weeks
            > 5_000_000
        ):
            raise HTTPException(
                status_code=413, detail="Instance exceeds the current model-size limit."
            )
        dataset = Dataset(
            owner_id=user.id,
            name=name.strip() or "Uploaded instance",
            payload=instance.model_dump(mode="json"),
            files={
                key: content.decode("utf-8-sig") for key, content in contents.items()
            },
            summary=instance.summary(),
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset
    finally:
        for file in files:
            await file.close()


@router.get("", response_model=list[DatasetResponse])
def list_instances(user: UserDependency, db: DatabaseDependency):
    return db.scalars(
        select(Dataset)
        .where(Dataset.owner_id == user.id)
        .order_by(Dataset.created_at.desc())
        .limit(100)
    ).all()


@router.get("/{dataset_id}")
def get_instance(dataset_id: str, user: UserDependency, db: DatabaseDependency):
    dataset = owned_dataset(db, dataset_id, user.id)
    return {
        **DatasetResponse.model_validate(dataset).model_dump(),
        "instance": dataset.payload,
    }
