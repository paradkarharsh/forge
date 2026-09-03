"""Security infrastructure tests."""
from uuid import uuid4

import jwt
import pytest

from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.security import (
    Argon2PasswordHasher,
    JwtTokenProvider,
    SecureRefreshTokenGenerator,
)
from forge_api.infrastructure.settings import get_settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv(
        "FORGE_DATABASE_URL",
        "postgresql+asyncpg://forge:secret@localhost:5432/forge",
    )
    monkeypatch.setenv("FORGE_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv(
        "FORGE_JWT_SECRET",
        "test-secret-that-is-at-least-32-characters-for-security-purposes",
    )
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()



class TestJwtTokenProvider:
    def test_roundtrip_encode_decode(self, settings) -> None:
        provider = JwtTokenProvider(settings)
        claims = AccessClaims(user_id=uuid4(), session_id=uuid4())
        token = provider.create_access_token(claims)
        decoded = provider.decode_access_token(token)
        assert decoded.user_id == claims.user_id
        assert decoded.session_id == claims.session_id

    def test_invalid_token_raises(self, settings) -> None:
        provider = JwtTokenProvider(settings)
        with pytest.raises(jwt.InvalidTokenError):
            provider.decode_access_token("garbage.not.jwt")

    def test_tampered_token_raises(self, settings) -> None:
        provider = JwtTokenProvider(settings)
        claims = AccessClaims(user_id=uuid4(), session_id=uuid4())
        token = provider.create_access_token(claims)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(jwt.InvalidTokenError):
            provider.decode_access_token(tampered)


class TestArgon2PasswordHasher:
    def test_hash_and_verify(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("mypassword")
        assert hasher.verify("mypassword", hashed)

    def test_wrong_password_fails(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("mypassword")
        assert not hasher.verify("wrongpassword", hashed)

    def test_hash_is_not_plaintext(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("secret123")
        assert hashed != "secret123"
        assert "$argon2" in hashed


class TestSecureRefreshTokenGenerator:
    def test_generate_produces_unique_tokens(self) -> None:
        gen = SecureRefreshTokenGenerator()
        tokens = {gen.generate() for _ in range(100)}
        assert len(tokens) == 100

    def test_digest_is_deterministic(self) -> None:
        gen = SecureRefreshTokenGenerator()
        token = gen.generate()
        assert gen.digest(token) == gen.digest(token)

    def test_different_tokens_have_different_digests(self) -> None:
        gen = SecureRefreshTokenGenerator()
        t1, t2 = gen.generate(), gen.generate()
        assert gen.digest(t1) != gen.digest(t2)

    def test_digest_is_hex_sha256(self) -> None:
        gen = SecureRefreshTokenGenerator()
        digest = gen.digest("test-token")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)
