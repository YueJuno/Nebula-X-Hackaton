from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def signing_key() -> str:
    key = get_settings().jwt_secret.get_secret_value()
    if len(key) < 32 or key.lower().startswith(("replace", "your_")):
        raise HTTPException(status_code=503, detail="Authentication is not configured. Set a random JWT_SECRET of at least 32 characters on the backend.")
    return key


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)},
        signing_key(), algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token, signing_key(), algorithms=[get_settings().jwt_algorithm],
        options={"require": ["sub", "iat", "exp"]},
    )
    return payload["sub"]
