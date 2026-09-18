from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # Liveness only: this does not check PostgreSQL or Redis connectivity.
    return HealthResponse(status="ok", service="scheduler-api")
