from redis.asyncio import Redis
from forge_api.infrastructure.settings import Settings
def create_cache_client(settings: Settings) -> Redis: return Redis.from_url(str(settings.redis_url), encoding="utf-8", decode_responses=True)
