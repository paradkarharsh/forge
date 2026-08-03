"""OAuth application service.

Orchestrates the full OAuth flow: authorize URL generation (with
state/nonce/PKCE), callback handling (state validation, code exchange,
user resolution), and token issuance.
"""
from datetime import UTC, datetime, timedelta

from forge_api.application.auth.dtos import OAuthIdentity, TokenPair
from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import AuthenticationError, ServiceUnavailableError
from forge_api.domain.repositories import (
    OAuthIdentityRepository,
    SessionRepository,
    UserRepository,
)
from forge_api.domain.security import (
    AccessClaims,
    RefreshTokenGenerator,
    TokenProvider,
)
from forge_api.infrastructure.audit import AuditLogger
from forge_api.infrastructure.oauth import (
    OAuthStateManager,
    build_authorize_url,
    derive_code_challenge,
    exchange_code,
)
from forge_api.infrastructure.settings import Settings


class OAuthService:
    """Handles the full server-side OAuth flow."""

    def __init__(
        self,
        *,
        users: UserRepository,
        oauth_identities: OAuthIdentityRepository,
        sessions: SessionRepository,
        tokens: TokenProvider,
        refresh: RefreshTokenGenerator,
        audit: AuditLogger,
        state_manager: OAuthStateManager,
        settings: Settings,
    ) -> None:
        self._users = users
        self._oauth = oauth_identities
        self._sessions = sessions
        self._tokens = tokens
        self._refresh = refresh
        self._audit = audit
        self._state = state_manager
        self._settings = settings
        self._refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)

    async def authorize_url(self, provider: str) -> dict[str, str]:
        """Generate an authorization URL with state, nonce, and PKCE."""
        redirect_uri = self._settings.oauth_redirect_uri.format(
            provider=provider
        )
        state, nonce, code_verifier = await self._state.create_state(provider)
        code_challenge = derive_code_challenge(code_verifier)

        url = await build_authorize_url(
            provider,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
            settings=self._settings,
        )

        self._audit.log(AuditEventType.OAUTH_AUTHORIZE, payload={"provider": provider})
        return {"authorize_url": url, "state": state}

    async def callback(
        self,
        provider: str,
        code: str,
        state: str,
        *,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str | None,
    ) -> TokenPair:
        """Handle the OAuth callback: validate state, exchange code, issue tokens."""
        # Validate state
        if not await self._state.validate_state(state, provider):
            self._audit.log(
                AuditEventType.OAUTH_STATE_MISMATCH,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"provider": provider},
            )
            raise AuthenticationError(
                "OAuth state validation failed", code="oauth_state_invalid"
            )

        # Consume PKCE code_verifier
        code_verifier = await self._state.consume_code_verifier(state)

        # Exchange code
        redirect_uri = self._settings.oauth_redirect_uri.format(
            provider=provider
        )
        try:
            profile = await exchange_code(
                provider,
                code,
                redirect_uri,
                self._settings,
                code_verifier=code_verifier,
            )
        except (RuntimeError, ValueError) as exc:
            raise ServiceUnavailableError(
                "OAuth provider is not configured"
            ) from exc

        # Extract subject
        subject = str(profile.get("sub") or profile.get("id") or "")
        if not subject:
            self._audit.log(
                AuditEventType.OAUTH_PROFILE_INVALID,
                ip_address=ip_address,
                payload={"provider": provider},
            )
            raise AuthenticationError(
                "OAuth provider response has no subject",
                code="oauth_profile_invalid",
            )

        # Resolve or create user
        email = profile.get("email")
        user = await self._resolve_user(
            OAuthIdentity(provider=provider, subject=subject, email=email)
        )

        # Issue tokens
        raw_refresh = self._refresh.generate()
        now = datetime.now(UTC)

        session = await self._sessions.create(
            user_id=user.id,
            family_id=user.id,
            refresh_hash=self._refresh.digest(raw_refresh),
            expires_at=now + self._refresh_ttl,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = self._tokens.create_access_token(
            AccessClaims(user_id=user.id, session_id=session.id)
        )

        # Consume nonce (validation is provider-specific; stored for auditing)
        nonce = await self._state.consume_nonce(state)

        self._audit.log(
            AuditEventType.OAUTH_CALLBACK,
            user_id=user.id,
            session_id=session.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"provider": provider, "nonce_present": nonce is not None},
        )

        return TokenPair(access_token=access_token, refresh_token=raw_refresh)

    async def _resolve_user(self, identity: OAuthIdentity):
        """Find or create a user from an OAuth identity."""
        linked = await self._oauth.find(identity.provider, identity.subject)
        if linked:
            user = await self._users.find_by_id(linked.user_id)
            if user:
                return user

        if not identity.email:
            raise AuthenticationError(
                "Provider did not supply a verified email",
                code="oauth_email_missing",
            )

        user = await self._users.find_by_email(identity.email)
        if not user:
            user = await self._users.create(
                email=identity.email, password_hash=None
            )

        await self._oauth.create(
            user_id=user.id,
            provider=identity.provider,
            subject=identity.subject,
        )
        return user
