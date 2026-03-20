from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except (JWTError, TypeError):
        return None


def _resolve_user(access_token: Optional[str], db: Session) -> Optional[models.User]:
    """Shared helper: returns a User or None."""
    if not access_token:
        return None
    user_id = decode_token(access_token)
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    user = _resolve_user(access_token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_current_user_or_redirect(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Same as get_current_user but redirects to /login for HTML pages."""
    user = _resolve_user(access_token, db)
    if not user:
        raise RedirectToLogin()
    return user


class RedirectToLogin(Exception):
    """Raised when a page requires auth — caught by middleware to redirect."""
    pass


def get_current_user_optional(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    if not access_token:
        return None
    user_id = decode_token(access_token)
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
