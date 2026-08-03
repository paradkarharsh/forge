from functools import lru_cache
from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FORGE_", extra="ignore")
    environment: str = "development"
    database_url: PostgresDsn
    redis_url: RedisDsn
    jwt_secret: SecretStr
    oauth_google_client_id: str | None = None
    oauth_google_client_secret: SecretStr | None = None
    oauth_github_client_id: str | None = None
    oauth_github_client_secret: SecretStr | None = None
@lru_cache
def get_settings() -> Settings: return Settings()
