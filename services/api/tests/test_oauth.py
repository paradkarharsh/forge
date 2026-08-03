from forge_api.application.auth.dtos import OAuthIdentity

def test_oauth_identity_preserves_provider_subject_and_email() -> None:
    identity=OAuthIdentity(provider="github",subject="123",email="person@example.com")
    assert identity.provider=="github"
    assert identity.subject=="123"
    assert identity.email=="person@example.com"
