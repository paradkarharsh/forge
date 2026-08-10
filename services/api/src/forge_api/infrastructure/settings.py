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

    # Repository intelligence / indexing
    index_max_file_bytes: int = 512 * 1024
    index_max_files: int = 50_000
    index_chunk_tokens: int = 256
    index_chunk_overlap: int = 32
    index_embedding_batch_size: int = 64
    index_timeout_seconds: int = 1_800
    index_worker_poll_seconds: int = 10
    index_git_timeout_seconds: int = 30
    # Start the background index worker as part of the app lifespan.
    index_worker_enabled: bool = True

    # Embeddings. "none" (default) disables embeddings via NullEmbedder so
    # structural search works without any ML dependency. "local" uses the
    # sentence-transformers all-MiniLM-L6-v2 model (384 dimensions).
    embedding_provider: str = "none"
    embedding_model: str = "all-MiniLM-L6-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
