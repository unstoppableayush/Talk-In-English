import logging

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

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        logger.info("Register attempt for email=%s", body.email)
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            logger.warning("Registration failed — email already exists: %s", body.email)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=body.email,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("User registered successfully: id=%s email=%s", user.id, user.email)

        tokens = TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            expires_in=900,
        )
        return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during registration for email=%s", body.email)
        raise HTTPException(status_code=500, detail="Internal server error during registration")


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        logger.info("Login attempt for email=%s", body.email)
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
            logger.warning("Login failed — invalid credentials for email=%s", body.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not user.is_active:
            logger.warning("Login failed — account deactivated: email=%s", body.email)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

        logger.info("User logged in: id=%s email=%s", user.id, user.email)
        tokens = TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            expires_in=900,
        )
        return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during login for email=%s", body.email)
        raise HTTPException(status_code=500, detail="Internal server error during login")


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Sign in or sign up with a Google ID token (from Google Sign-In)."""
    logger.info("Google auth attempt")
    if not settings.GOOGLE_CLIENT_ID:
        logger.error("Google login not configured — GOOGLE_CLIENT_ID is empty")
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
        logger.info("Google token verified successfully")
    except ValueError:
        logger.warning("Google token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_id: str = idinfo["sub"]
    email: str = idinfo.get("email", "")
    name: str = idinfo.get("name", email.split("@")[0])
    picture: str | None = idinfo.get("picture")
    logger.info("Google user info: email=%s, google_id=%s", email, google_id)

    if not email:
        logger.warning("Google account has no email for google_id=%s", google_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    try:
        # Look up by google_id first, then by email
        logger.debug("Looking up user by google_id=%s", google_id)
        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.debug("No user found by google_id, checking email=%s", email)
            # Check if email already exists (link accounts)
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user:
                # Link Google to existing email account
                logger.info("Linking Google account to existing user id=%s", user.id)
                user.google_id = google_id
                if not user.avatar_url and picture:
                    user.avatar_url = picture
            else:
                # Create new user
                logger.info("Creating new user for email=%s", email)
                user = User(
                    email=email,
                    display_name=name,
                    google_id=google_id,
                    avatar_url=picture,
                )
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info("User saved: id=%s", user.id)
        else:
            logger.info("Existing user found: id=%s", user.id)

        if not user.is_active:
            logger.warning("Google auth denied — account deactivated: id=%s", user.id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

        tokens = TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            expires_in=900,
        )
        logger.info("Google auth successful for user id=%s", user.id)
        return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during Google auth for email=%s", email)
        raise HTTPException(status_code=500, detail="Internal server error during Google auth")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        logger.info("Token refresh attempt")
        payload = decode_token(body.refresh_token)
        if payload is None or payload.get("type") != "refresh":
            logger.warning("Token refresh failed — invalid refresh token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_id = payload.get("sub")
        logger.debug("Refreshing token for user_id=%s", user_id)
        result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("Token refresh failed — user not found: user_id=%s", user_id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        logger.info("Token refreshed for user id=%s", user.id)
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            expires_in=900,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during token refresh")
        raise HTTPException(status_code=500, detail="Internal server error during token refresh")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info("Profile update for user id=%s", user.id)
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
        logger.info("Profile updated for user id=%s", user.id)
        return UserResponse.model_validate(user)
    except Exception:
        logger.exception("Unexpected error updating profile for user id=%s", user.id)
        raise HTTPException(status_code=500, detail="Internal server error updating profile")
