from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
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

    # Context and memory engine
    memory_embedding_backfill_batch_size: int = Field(default=100, gt=0)
    memory_maintenance_interval_seconds: int = Field(default=3600, gt=0)
    memory_max_content_length: int = Field(default=16_384, gt=0)
    memory_max_tags: int = Field(default=20, gt=0)
    memory_maintenance_worker_enabled: bool = True
    context_max_tokens: int = Field(default=8192, ge=256, le=65_536)
    context_min_relevance: float = Field(default=0.1, ge=0.0, le=1.0)
    context_conversation_max_entries: int = Field(default=100, gt=0)
    context_conversation_ttl_seconds: int = Field(default=86_400, gt=0)
    context_rank_semantic_weight: float = Field(default=0.40, ge=0.0, le=1.0)
    context_rank_recency_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    context_rank_confidence_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    context_rank_scope_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    context_rank_type_weight: float = Field(default=0.10, ge=0.0, le=1.0)

    # ─── LLM / AI ──────────────────────────────────────────────────────
    llm_default_model: str = "fake/echo"
    llm_default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_default_max_tokens: int = Field(default=4096, gt=0, le=128_000)
    llm_request_timeout_seconds: int = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_max_query_length: int = Field(default=32_768, gt=0)
    llm_max_output_tokens: int = Field(default=16_384, gt=0)

    # Provider API keys — NEVER stored in PostgreSQL.
    llm_openai_api_key: SecretStr | None = None
    llm_openai_base_url: str = "https://api.openai.com/v1"
    llm_ollama_base_url: str = "http://localhost:11434"

    # Prompt builder
    prompt_version: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
