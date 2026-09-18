from pathlib import Path

from app.core.config import Settings


def test_env_file_is_in_backend():
    assert Settings.model_config["env_file"] == Path(__file__).resolve().parents[1] / ".env"


def test_signup_code_and_signing_key_load_from_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNUP_CODE", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SIGNUP_CODE=custom-code\nJWT_SECRET=a-test-signing-key-with-32-characters\n")
    settings = Settings(_env_file=env_file)
    assert settings.signup_code.get_secret_value() == "custom-code"
    assert settings.jwt_secret.get_secret_value() == "a-test-signing-key-with-32-characters"
