"""JWT-based authentication utilities for the API layer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

try:
    from jose import JWTError, jwt  # type: ignore
    _JOSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JOSE_AVAILABLE = False
    logger.warning("python-jose not installed; JWT auth disabled")

try:
    from passlib.context import CryptContext  # type: ignore
    _PASSLIB_AVAILABLE = True
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:  # pragma: no cover
    _PASSLIB_AVAILABLE = False
    pwd_context = None  # type: ignore
    logger.warning("passlib not installed; password hashing disabled")

from app.config import settings
from app.models.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*.

    Args:
        plain: Plain-text password.

    Returns:
        Bcrypt hash string.
    """
    if not _PASSLIB_AVAILABLE:
        return plain  # Dev fallback — never use in production
    return pwd_context.hash(plain)  # type: ignore[union-attr]


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain: Plain-text password.
        hashed: Stored bcrypt hash.

    Returns:
        True if the password matches.
    """
    if not _PASSLIB_AVAILABLE:
        return plain == hashed
    try:
        return pwd_context.verify(plain, hashed)  # type: ignore[union-attr]
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: str,
    username: str,
    roles: list[str],
    tenant_id: str = "default",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: Subject user ID.
        username: Username.
        roles: List of role strings.
        tenant_id: Tenant identifier.
        expires_delta: Optional custom expiry duration.

    Returns:
        Encoded JWT string.
    """
    if not _JOSE_AVAILABLE:
        # Return a stub token in dev environments
        return f"dev-token-{user_id}"

    expire = datetime.now(UTC) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "tenant_id": tenant_id,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        :class:`TokenData` or *None* if invalid.
    """
    if not _JOSE_AVAILABLE:
        return TokenData(user_id="dev-user", username="dev", roles=["admin"])

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            user_id=payload.get("sub"),
            username=payload.get("username"),
            roles=payload.get("roles", []),
            tenant_id=payload.get("tenant_id", "default"),
        )
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> TokenData:
    """FastAPI dependency: validate the bearer token and return token data.

    Args:
        token: Bearer token extracted by OAuth2PasswordBearer.

    Returns:
        Decoded :class:`TokenData`.

    Raises:
        HTTPException: 401 if the token is missing or invalid.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


async def require_role(required_role: str, current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """FastAPI dependency that requires a specific role.

    Args:
        required_role: Role string that must be present.
        current_user: Injected token data.

    Returns:
        :class:`TokenData`.

    Raises:
        HTTPException: 403 if the user does not have the required role.
    """
    if required_role not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{required_role}' required",
        )
    return current_user
