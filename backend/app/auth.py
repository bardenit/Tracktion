from datetime import datetime, timedelta, timezone
import hashlib
import uuid
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import RefreshSession, User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(data: dict, jti: Optional[str] = None, family_id: Optional[str] = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": jti or str(uuid.uuid4()),
        "family": family_id or str(uuid.uuid4()),
    })
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def hash_refresh_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def persist_refresh_session(db: Session, user_id: int, token: str) -> RefreshSession:
    payload = verify_token(token)
    session = RefreshSession(
        user_id=user_id,
        jti_hash=hash_refresh_jti(payload["jti"]),
        family_id=payload["family"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None),
    )
    db.add(session)
    return session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user"""
    token = credentials.credentials
    
    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user
