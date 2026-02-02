"""Security utilities for authentication and authorization."""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.config import settings
from app.models.user import UserRole

# Initialize Argon2 password hasher with secure defaults
password_hasher = PasswordHasher(
    time_cost=3,  # Number of iterations
    memory_cost=65536,  # 64 MB
    parallelism=4,  # Number of parallel threads
    hash_len=32,  # Length of the hash in bytes
    salt_len=16,  # Length of the salt in bytes
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_hasher.verify(hashed_password, password)
        return True
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This is useful when password hashing parameters change.

    Args:
        hashed_password: Existing password hash

    Returns:
        True if rehash is needed, False otherwise
    """
    return password_hasher.check_needs_rehash(hashed_password)


def _get_private_key() -> str:
    """Get the JWT private key for signing tokens."""
    if settings.jwt_private_key:
        # Decode from base64 if provided
        try:
            return base64.b64decode(settings.jwt_private_key).decode("utf-8")
        except Exception:
            return settings.jwt_private_key

    # Fallback for development (use secret key with HS256)
    return settings.secret_key


def _get_public_key() -> str:
    """Get the JWT public key for verifying tokens."""
    if settings.jwt_public_key:
        # Decode from base64 if provided
        try:
            return base64.b64decode(settings.jwt_public_key).decode("utf-8")
        except Exception:
            return settings.jwt_public_key

    # Fallback for development (use secret key with HS256)
    return settings.secret_key


def _get_algorithm() -> str:
    """Get the JWT algorithm to use."""
    # If no private key is set, fall back to HS256 for development
    if not settings.jwt_private_key:
        return "HS256"
    return settings.jwt_algorithm


def create_access_token(
    user_id: str,
    role: UserRole,
    session_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User ID to encode in token
        role: User role to encode in token
        session_id: Session ID for token tracking
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT access token
    """
    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "role": role.value,
        "session_id": session_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),  # JWT ID for blacklisting
        "type": "access",
    }

    return jwt.encode(
        payload,
        _get_private_key(),
        algorithm=_get_algorithm(),
    )


def create_refresh_token(
    user_id: str,
    session_id: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    """
    Create a JWT refresh token.

    Args:
        user_id: User ID to encode in token
        session_id: Session ID for token tracking
        expires_delta: Optional custom expiration time

    Returns:
        Tuple of (encoded JWT refresh token, token JTI)
    """
    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(days=settings.refresh_token_expire_days)
    expire = now + expires_delta

    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "session_id": session_id,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }

    token = jwt.encode(
        payload,
        _get_private_key(),
        algorithm=_get_algorithm(),
    )

    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        algorithm = _get_algorithm()
        if algorithm.startswith("RS") or algorithm.startswith("ES"):
            key = _get_public_key()
        else:
            key = _get_private_key()

        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
        )
        return payload
    except JWTError:
        raise


def get_token_expiry_seconds(token: str) -> int:
    """
    Get the remaining time until token expiry in seconds.

    Args:
        token: JWT token

    Returns:
        Seconds until expiry (0 if already expired)
    """
    try:
        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        remaining = (exp - now).total_seconds()
        return max(0, int(remaining))
    except (JWTError, KeyError):
        return 0


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())
