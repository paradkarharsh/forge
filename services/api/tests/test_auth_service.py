"""AuthService unit tests."""
import pytest

from forge_api.application.auth.auth_service import AuthService
from forge_api.domain.errors import AuthenticationError, ConflictError


@pytest.fixture
def auth_service(fake_users, fake_sessions, fake_tokens, fake_passwords, fake_refresh, fake_audit):
    return AuthService(
        users=fake_users,
        sessions=fake_sessions,
        tokens=fake_tokens,
        passwords=fake_passwords,
        refresh=fake_refresh,
        audit=fake_audit,
        refresh_ttl_days=30,
    )


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_creates_user_and_returns_tokens(
        self, auth_service, fake_users
    ) -> None:
        pair = await auth_service.register(
            email="new@example.com",
            password="supersecure12",
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            device_name="Linux",
        )
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"
        user = await fake_users.find_by_email("new@example.com")
        assert user is not None

    @pytest.mark.asyncio
    async def test_register_rejects_duplicate_email(
        self, auth_service, fake_users
    ) -> None:
        await auth_service.register(
            email="dup@example.com",
            password="supersecure12",
            ip_address=None,
            user_agent=None,
            device_name=None,
        )
        with pytest.raises(ConflictError, match="already registered"):
            await auth_service.register(
                email="dup@example.com",
                password="supersecure12",
                ip_address=None,
                user_agent=None,
                device_name=None,
            )

    @pytest.mark.asyncio
    async def test_register_audits_event(
        self, auth_service, fake_audit
    ) -> None:
        await auth_service.register(
            email="audit@example.com",
            password="supersecure12",
            ip_address="10.0.0.1",
            user_agent="UA",
            device_name=None,
        )
        assert any(e["event"].value == "auth.register" for e in fake_audit.events)


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_succeeds_with_valid_credentials(
        self, auth_service
    ) -> None:
        await auth_service.register(
            email="login@example.com",
            password="correctpasswd",
            ip_address=None,
            user_agent=None,
            device_name=None,
        )
        pair = await auth_service.login(
            email="login@example.com",
            password="correctpasswd",
            ip_address=None,
            user_agent=None,
            device_name=None,
        )
        assert pair.access_token
        assert pair.refresh_token

    @pytest.mark.asyncio
    async def test_login_rejects_wrong_password(self, auth_service) -> None:
        await auth_service.register(
            email="wrong@example.com",
            password="correctpasswd",
            ip_address=None,
            user_agent=None,
            device_name=None,
        )
        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await auth_service.login(
                email="wrong@example.com",
                password="wrongpassword",
                ip_address=None,
                user_agent=None,
                device_name=None,
            )

    @pytest.mark.asyncio
    async def test_login_rejects_unknown_email(self, auth_service) -> None:
        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await auth_service.login(
                email="nobody@example.com",
                password="whatever1234",
                ip_address=None,
                user_agent=None,
                device_name=None,
            )
