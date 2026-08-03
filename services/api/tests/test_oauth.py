"""OAuth DTO and PKCE tests."""
from forge_api.application.auth.dtos import OAuthIdentity, TokenPair
from forge_api.infrastructure.oauth import derive_code_challenge, generate_code_verifier


class TestOAuthIdentity:
    def test_preserves_fields(self) -> None:
        identity = OAuthIdentity(provider="github", subject="123", email="x@y.com")
        assert identity.provider == "github"
        assert identity.subject == "123"
        assert identity.email == "x@y.com"

    def test_email_optional(self) -> None:
        identity = OAuthIdentity(provider="google", subject="456", email=None)
        assert identity.email is None


class TestTokenPair:
    def test_default_token_type(self) -> None:
        pair = TokenPair(access_token="a", refresh_token="r")
        assert pair.token_type == "bearer"


class TestPKCE:
    def test_code_verifier_length(self) -> None:
        verifier = generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_code_verifier_uniqueness(self) -> None:
        verifiers = {generate_code_verifier() for _ in range(50)}
        assert len(verifiers) == 50

    def test_code_challenge_is_deterministic(self) -> None:
        verifier = generate_code_verifier()
        c1 = derive_code_challenge(verifier)
        c2 = derive_code_challenge(verifier)
        assert c1 == c2

    def test_different_verifiers_produce_different_challenges(self) -> None:
        v1, v2 = generate_code_verifier(), generate_code_verifier()
        assert derive_code_challenge(v1) != derive_code_challenge(v2)

    def test_challenge_is_base64url_no_padding(self) -> None:
        challenge = derive_code_challenge(generate_code_verifier())
        assert "=" not in challenge
        assert all(c.isalnum() or c in "-_" for c in challenge)
