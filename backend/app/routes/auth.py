from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models import RefreshSession, User
from app.schemas import UserCreate, UserLogin, TokenResponse, UserResponse, RefreshRequest, ChangePasswordRequest
from app.auth import (
    create_access_token, create_refresh_token, get_current_user, hash_password,
    hash_refresh_jti, persist_refresh_session, verify_password, verify_token,
)
from app.limiter import limiter

router = APIRouter()


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).count() > 0:
        raise HTTPException(status_code=403, detail="Registration is closed")
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="Account locked. Try again later.")

    if not user or not verify_password(credentials.password, user.password_hash):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            user.last_failed_login_at = datetime.now(timezone.utc)
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    db.commit()

    refresh_token = create_refresh_token({"sub": str(user.id)})
    persist_refresh_session(db, user.id, refresh_token)
    db.commit()
    return TokenResponse(access_token=create_access_token({"sub": str(user.id)}), refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    payload = verify_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        user_id = int(payload.get("sub"))
        jti_hash = hash_refresh_jti(payload["jti"])
        family_id = payload["family"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    session = db.query(RefreshSession).filter(RefreshSession.jti_hash == jti_hash).first()
    if not session or session.user_id != user_id or session.family_id != family_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if session.revoked_at is not None or session.expires_at <= now:
        db.query(RefreshSession).filter(RefreshSession.family_id == family_id).update(
            {RefreshSession.revoked_at: now}, synchronize_session=False
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token replay detected")
    claimed = db.query(RefreshSession).filter(
        RefreshSession.id == session.id, RefreshSession.revoked_at.is_(None)
    ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
    if claimed != 1:
        db.rollback()
        db.query(RefreshSession).filter(RefreshSession.family_id == family_id).update(
            {RefreshSession.revoked_at: now}, synchronize_session=False
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token replay detected")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        db.rollback()
        raise HTTPException(status_code=401, detail="User not found")
    refresh_token = create_refresh_token({"sub": str(user.id)}, family_id=family_id)
    persist_refresh_session(db, user.id, refresh_token)
    db.commit()
    return TokenResponse(access_token=create_access_token({"sub": str(user.id)}), refresh_token=refresh_token)


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = verify_token(body.refresh_token)
    if payload and payload.get("type") == "refresh" and payload.get("jti"):
        db.query(RefreshSession).filter(
            RefreshSession.jti_hash == hash_refresh_jti(payload["jti"]),
            RefreshSession.revoked_at.is_(None),
        ).update({RefreshSession.revoked_at: datetime.now(timezone.utc).replace(tzinfo=None)}, synchronize_session=False)
        db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/needs-setup")
def needs_setup(db: Session = Depends(get_db)):
    return {"needs_setup": db.query(User).count() == 0}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    db.query(RefreshSession).filter(
        RefreshSession.user_id == current_user.id,
        RefreshSession.revoked_at.is_(None),
    ).update({RefreshSession.revoked_at: datetime.now(timezone.utc).replace(tzinfo=None)}, synchronize_session=False)
    db.commit()
    return {"message": "Password updated"}
