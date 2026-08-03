from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str | None
