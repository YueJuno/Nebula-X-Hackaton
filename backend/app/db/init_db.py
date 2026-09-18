"""Run with: python -m app.db.init_db (from backend)."""
from app.db.session import Base, get_engine
from app.models.user import User  # noqa: F401
from app.models.scheduling import Dataset, Run  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(get_engine())
    print("Database tables initialized.")
