"""Async Redis client factory.

A single shared Redis connection is created on first use and reused across
requests. Call close() during application shutdown to drain the connection pool.
"""

from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio.client import Redis as RedisClient

from app.shared.config import settings

_client: RedisClient | None = None


async def get_redis() -> RedisClient:
    """Return the shared async Redis client, creating it on first call."""
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool — call during application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
