import logging
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

logger = logging.getLogger(__name__)
security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload is None or payload.get("type") != "access":
            logger.warning("Invalid access token presented")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user_id = payload.get("sub")
        logger.debug("Authenticating user_id=%s", user_id)
        result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("User not found or inactive: user_id=%s", user_id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_current_user")
        raise HTTPException(status_code=500, detail=f"Internal server error during authentication: {e}")


def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory that checks the current user has one of the allowed roles.
    Usage:  user: User = Depends(require_role("admin", "moderator"))
    """
    async def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have access. Required: {', '.join(allowed_roles)}",
            )
        return user

    return _role_checker


# Convenient pre-built dependencies
require_admin = require_role("admin")
require_moderator = require_role("admin", "moderator")
