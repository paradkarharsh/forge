"""Security port contracts.

Application services depend on these protocols so that token, hashing, and
randomness primitives stay behind stable seams implemented in the
infrastructure layer.
"""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """Claims carried by a short-lived access token."""

    user_id: UUID
    session_id: UUID


class TokenProvider(Protocol):
    def create_access_token(self, claims: AccessClaims) -> str: ...

    def decode_access_token(self, token: str) -> AccessClaims: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hashed: str) -> bool: ...


class RefreshTokenGenerator(Protocol):
    def generate(self) -> str: ...

    def digest(self, token: str) -> str: ...
