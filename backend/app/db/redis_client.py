import redis
from app.core.config import settings

# Synchronous Redis client with hiredis parser for speed.
# decode_responses=True so all values come back as str, not bytes.
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


def get_redis() -> redis.Redis:
    """FastAPI dependency — returns the shared Redis client."""
    return redis_client


def ping_redis() -> bool:
    """Returns True if Redis is reachable."""
    try:
        return redis_client.ping()
    except Exception:
        return False
