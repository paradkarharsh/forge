from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FORGE_", extra="ignore")

    environment: str = "development"
    database_url: PostgresDsn
    redis_url: RedisDsn
    jwt_secret: SecretStr

    # Access tokens are short-lived and unrevocable by themselves; sessions
    # gate revocation server-side through the session id claim.
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    # How long a session id must be idle before the throttle allows a
    # last_active update again.
    session_last_active_throttle_seconds: int = 60
    session_cleanup_interval_seconds: int = 3600

    # OAuth
    oauth_google_client_id: str | None = None
    oauth_google_client_secret: SecretStr | None = None
    oauth_github_client_id: str | None = None
    oauth_github_client_secret: SecretStr | None = None
    oauth_state_ttl_seconds: int = 600
    oauth_redirect_uri: str = "http://localhost:8000/v1/oauth/{provider}/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
