from datetime import timedelta

from app.auth import create_access_token, create_refresh_token, verify_token


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
