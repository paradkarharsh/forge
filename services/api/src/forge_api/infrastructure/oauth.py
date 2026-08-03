"""OAuth provider infrastructure.

Handles code exchange plus state, PKCE code_verifier, and nonce
generation and validation backed by Redis for short-lived storage.
"""
import hashlib
import secrets
from base64 import urlsafe_b64encode

from authlib.integrations.httpx_client import AsyncOAuth2Client
from redis.asyncio import Redis

from forge_api.infrastructure.settings import Settings

PROVIDERS: dict[str, tuple[str, str, str]] = {
    "google": (
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/oauth2/v3/userinfo",
    ),
    "github": (
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        "https://api.github.com/user",
    ),
}

_STATE_PREFIX = "oauth:state:"
_NONCE_PREFIX = "oauth:nonce:"
_PKCE_PREFIX = "oauth:pkce:"


def _provider_credentials(
    name: str, settings: Settings
) -> tuple[str, str, str, str, str]:
    """Return (authorize_url, token_url, userinfo_url, client_id, secret)."""
    if name == "google":
        client_id = settings.oauth_google_client_id
        secret_value = settings.oauth_google_client_secret
    elif name == "github":
        client_id = settings.oauth_github_client_id
        secret_value = settings.oauth_github_client_secret
    else:
        raise ValueError(f"Unsupported OAuth provider: {name}")

    if not client_id or not secret_value:
        raise RuntimeError(f"{name} OAuth is not configured")

    return (*PROVIDERS[name], client_id, secret_value.get_secret_value())


def generate_code_verifier() -> str:
    """Generate a PKCE code_verifier (RFC 7636)."""
    return secrets.token_urlsafe(64)[:128]


def derive_code_challenge(verifier: str) -> str:
    """Derive the S256 code_challenge from a code_verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class OAuthStateManager:
    """Manages transient OAuth state/nonce/PKCE values in Redis."""

    def __init__(self, cache: Redis, settings: Settings) -> None:
        self._cache = cache
        self._ttl = settings.oauth_state_ttl_seconds

    async def create_state(
        self, provider: str, *, nonce: str | None = None
    ) -> tuple[str, str | None, str]:
        """Return (state, nonce, code_verifier)."""
        state = secrets.token_urlsafe(32)
        code_verifier = generate_code_verifier()

        await self._cache.setex(
            f"{_STATE_PREFIX}{state}", self._ttl, provider
        )
        await self._cache.setex(
            f"{_PKCE_PREFIX}{state}", self._ttl, code_verifier
        )

        if nonce is None:
            nonce = secrets.token_urlsafe(32)
        await self._cache.setex(f"{_NONCE_PREFIX}{state}", self._ttl, nonce)

        return state, nonce, code_verifier

    async def validate_state(self, state: str, provider: str) -> bool:
        """Consume state and verify it matches the expected provider."""
        stored = await self._cache.getdel(f"{_STATE_PREFIX}{state}")
        return stored is not None and stored == provider

    async def consume_nonce(self, state: str) -> str | None:
        """Consume and return the nonce associated with the state."""
        return await self._cache.getdel(f"{_NONCE_PREFIX}{state}")

    async def consume_code_verifier(self, state: str) -> str | None:
        """Consume and return the code_verifier associated with the state."""
        return await self._cache.getdel(f"{_PKCE_PREFIX}{state}")


async def build_authorize_url(
    provider: str,
    *,
    state: str,
    nonce: str,
    code_challenge: str,
    redirect_uri: str,
    settings: Settings,
) -> str:
    """Build the provider's authorization URL with state, nonce, and PKCE."""
    auth_url, _, _, client_id, _ = _provider_credentials(provider, settings)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }

    if provider == "google":
        params["scope"] = "openid email profile"
        params["nonce"] = nonce
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    elif provider == "github":
        params["scope"] = "user:email"

    from urllib.parse import urlencode

    return f"{auth_url}?{urlencode(params)}"


async def exchange_code(
    provider: str,
    code: str,
    redirect_uri: str,
    settings: Settings,
    *,
    code_verifier: str | None = None,
) -> dict:
    """Exchange an authorization code for a user profile dictionary."""
    _, token_url, userinfo_url, client_id, secret = _provider_credentials(
        provider, settings
    )

    kwargs: dict = {"code": code, "redirect_uri": redirect_uri}
    if code_verifier:
        kwargs["code_verifier"] = code_verifier

    headers = {"Accept": "application/json"}

    async with AsyncOAuth2Client(client_id, secret) as client:
        token = await client.fetch_token(
            token_url, headers=headers, **kwargs
        )
        response = await client.get(userinfo_url, token=token)
        response.raise_for_status()
        return response.json()
