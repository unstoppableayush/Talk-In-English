from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.models import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=900,
    )
    return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    tokens = TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=900,
    )
    return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Sign in or sign up with a Google ID token (from Google Sign-In)."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google login is not configured",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_id: str = idinfo["sub"]
    email: str = idinfo.get("email", "")
    name: str = idinfo.get("name", email.split("@")[0])
    picture: str | None = idinfo.get("picture")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # Look up by google_id first, then by email
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # Check if email already exists (link accounts)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Link Google to existing email account
            user.google_id = google_id
            if not user.avatar_url and picture:
                user.avatar_url = picture
        else:
            # Create new user
            user = User(
                email=email,
                display_name=name,
                google_id=google_id,
                avatar_url=picture,
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    tokens = TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=900,
    )
    return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=900,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    if body.native_language is not None:
        user.native_language = body.native_language
    if body.target_language is not None:
        user.target_language = body.target_language

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
