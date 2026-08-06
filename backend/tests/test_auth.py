from datetime import timedelta
import stat

from app.auth import create_access_token, create_refresh_token, verify_token
from app.config import load_or_create_jwt_secret, resolve_jwt_secret


def test_generated_jwt_secret_persists_across_restarts(tmp_path):
    secret_path = tmp_path / ".jwt_secret"

    first_secret = load_or_create_jwt_secret(secret_path)
    second_secret = load_or_create_jwt_secret(secret_path)

    assert first_secret == second_secret
    assert len(first_secret) >= 32
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600


def test_explicit_jwt_secret_takes_precedence(tmp_path, monkeypatch):
    secret_path = tmp_path / ".jwt_secret"
    explicit_secret = "a" * 48
    monkeypatch.setenv("JWT_SECRET_KEY", explicit_secret)

    assert resolve_jwt_secret(secret_path) == explicit_secret
    assert not secret_path.exists()


def test_legacy_default_is_replaced_with_persisted_secret(tmp_path, monkeypatch):
    secret_path = tmp_path / ".jwt_secret"
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-in-production")

    generated_secret = resolve_jwt_secret(secret_path)

    assert generated_secret != "change-me-in-production"
    assert generated_secret == secret_path.read_text()


def test_tokens_have_distinct_purposes():
    assert verify_token(create_access_token({"sub": "1"}))["type"] == "access"
    assert verify_token(create_refresh_token({"sub": "1"}))["type"] == "refresh"


def test_refresh_token_is_rejected_as_access_token(db_session):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    from app.auth import get_current_user

    token = create_refresh_token({"sub": "1"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    try:
        import asyncio
        asyncio.run(get_current_user(credentials, db_session))
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("refresh token was accepted as access token")


def test_malformed_subject_is_rejected_defensively(db_session):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    from app.auth import get_current_user
    import asyncio

    token = create_access_token({"sub": "not-an-int"}, timedelta(minutes=1))
    try:
        asyncio.run(get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db_session))
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("malformed subject was accepted")
