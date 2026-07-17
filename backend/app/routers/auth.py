import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TokenOut, UserLogin, UserOut, UserRegister
from app.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> TokenOut:
    email = payload.email.strip().lower()
    try:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(email=email, password_hash=hash_password(payload.password))
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return TokenOut(access_token=create_access_token(user.id))
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Register failed for %s", email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {exc.__class__.__name__}: {exc}",
        ) from exc


@router.post("/login", response_model=TokenOut)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenOut:
    email = payload.email.strip().lower()
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return TokenOut(access_token=create_access_token(user.id))
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Login failed for %s", email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {exc.__class__.__name__}: {exc}",
        ) from exc


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
