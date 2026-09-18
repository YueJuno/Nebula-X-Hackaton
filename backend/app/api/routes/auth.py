import secrets

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password, signing_key, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Credentials, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


def token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    expected = get_settings().signup_code.get_secret_value()
    if not expected or not secrets.compare_digest(
        payload.signup_code.get_secret_value().encode(), expected.encode()
    ):
        raise HTTPException(status_code=403, detail="Invalid signup code.")
    signing_key()  # Fail before creating an account if signing is not configured.
    user = User(email=str(payload.email), password_hash=hash_password(payload.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    db.refresh(user)
    return token_response(user)


@router.post("/signin", response_model=TokenResponse)
def signin(payload: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None or not verify_password(payload.password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return token_response(user)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=401, detail="Sign in again to continue.", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user
