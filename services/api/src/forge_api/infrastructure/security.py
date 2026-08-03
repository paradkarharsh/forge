"""Infrastructure implementations of the domain security protocols.

Each class satisfies a single domain protocol so application services
never depend on JWT, Argon2 or hashing libraries directly.
"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.settings import Settings

_passwords = PasswordHash.recommended()


class JwtTokenProvider:
    """Issues and verifies short-lived JWTs containing user+session claims."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._ttl = timedelta(minutes=settings.access_token_ttl_minutes)
        self._algorithm = "HS256"

    def create_access_token(self, claims: AccessClaims) -> str:
        payload = {
            "sub": str(claims.user_id),
            "sid": str(claims.session_id),
            "exp": datetime.now(UTC) + self._ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AccessClaims:
        data = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        return AccessClaims(
            user_id=UUID(data["sub"]),
            session_id=UUID(data["sid"]),
        )


class Argon2PasswordHasher:
    """Argon2id password hashing via pwdlib."""

    def hash(self, password: str) -> str:
        return _passwords.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return _passwords.verify(password, hashed)


class SecureRefreshTokenGenerator:
    """Generates cryptographically random refresh tokens and their digests."""

    def generate(self) -> str:
        return token_urlsafe(48)

    def digest(self, token: str) -> str:
        return sha256(token.encode()).hexdigest()
