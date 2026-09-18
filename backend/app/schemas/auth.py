from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Credentials(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr):
        password = value.get_secret_value()
        if len(password) < 8 or len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be at least 8 characters and at most 72 UTF-8 bytes.")
        return value


class SignupRequest(Credentials):
    signup_code: SecretStr = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
