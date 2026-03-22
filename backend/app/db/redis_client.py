"""Async Redis client with caching helpers and stream support."""

import functools
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False
    logger.warning("redis package not installed; Redis features disabled")

from app.config import settings


class RedisClient:
    """Async Redis wrapper with JSON serialisation helpers.

    All public methods degrade gracefully when the Redis connection is
    unavailable rather than raising unhandled exceptions.

    Attributes:
        _client: Underlying async Redis client once connected.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the connection pool and verify the server is reachable."""
        if not _REDIS_AVAILABLE:
            logger.warning("Redis client library not installed; skipping")
            return
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await self._client.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)

    async def close(self) -> None:
        """Close all Redis connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        if not self._client:
            logger.warning("Redis client not initialised")
            return False
        return True

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value)

    @staticmethod
    def _deserialize(raw: Optional[str]) -> Any:
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw

    # ------------------------------------------------------------------
    # Basic KV
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Any:
        """Retrieve and deserialize a stored value.

        Args:
            key: Redis key.

        Returns:
            Deserialized value or *None*.
        """
        if not self._is_connected():
            return None
        raw = await self._client.get(key)
        return self._deserialize(raw)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize and store a value.

        Args:
            key: Redis key.
            value: Value to store (will be JSON-serialized unless str).
            ttl: Optional TTL in seconds.

        Returns:
            True if stored successfully.
        """
        if not self._is_connected():
            return False
        serialized = self._serialize(value)
        if ttl:
            await self._client.setex(key, ttl, serialized)
        else:
            await self._client.set(key, serialized)
        return True

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys.

        Args:
            keys: Redis keys to delete.

        Returns:
            Number of keys deleted.
        """
        if not self._is_connected():
            return 0
        return await self._client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """Check whether a key exists.

        Args:
            key: Redis key.

        Returns:
            True if the key exists.
        """
        if not self._is_connected():
            return False
        return bool(await self._client.exists(key))

    async def expire(self, key: str, seconds: int) -> bool:
        """Set or update the TTL for an existing key.

        Args:
            key: Redis key.
            seconds: New TTL in seconds.

        Returns:
            True if the TTL was set.
        """
        if not self._is_connected():
            return False
        return bool(await self._client.expire(key, seconds))

    # ------------------------------------------------------------------
    # Hash
    # ------------------------------------------------------------------

    async def hget(self, name: str, key: str) -> Any:
        """Get a single field from a hash.

        Args:
            name: Hash name.
            key: Field name.

        Returns:
            Deserialized field value or *None*.
        """
        if not self._is_connected():
            return None
        raw = await self._client.hget(name, key)
        return self._deserialize(raw)

    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set a single hash field.

        Args:
            name: Hash name.
            key: Field name.
            value: Value (will be serialized).

        Returns:
            Number of new fields added.
        """
        if not self._is_connected():
            return 0
        return await self._client.hset(name, key, self._serialize(value))

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete fields from a hash.

        Args:
            name: Hash name.
            keys: Fields to delete.

        Returns:
            Number of fields deleted.
        """
        if not self._is_connected():
            return 0
        return await self._client.hdel(name, *keys)

    async def hgetall(self, name: str) -> dict:
        """Get all fields and values of a hash.

        Args:
            name: Hash name.

        Returns:
            Dict of field → deserialized value.
        """
        if not self._is_connected():
            return {}
        raw = await self._client.hgetall(name)
        return {k: self._deserialize(v) for k, v in raw.items()}

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to the head of a list.

        Args:
            key: Redis key.
            values: Values to push (will be serialized).

        Returns:
            New list length.
        """
        if not self._is_connected():
            return 0
        serialized = [self._serialize(v) for v in values]
        return await self._client.lpush(key, *serialized)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list:
        """Get a range of elements from a list.

        Args:
            key: Redis key.
            start: Start index (inclusive).
            end: End index (inclusive, -1 = last).

        Returns:
            List of deserialized values.
        """
        if not self._is_connected():
            return []
        raw = await self._client.lrange(key, start, end)
        return [self._deserialize(v) for v in raw]

    # ------------------------------------------------------------------
    # Pub/Sub
    # ------------------------------------------------------------------

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a Redis channel.

        Args:
            channel: Channel name.
            message: Message payload (will be serialized).

        Returns:
            Number of subscribers that received the message.
        """
        if not self._is_connected():
            return 0
        return await self._client.publish(channel, self._serialize(message))

    async def subscribe(self, *channels: str) -> Any:
        """Create a pub/sub subscription to one or more channels.

        Args:
            channels: Channel names to subscribe to.

        Returns:
            PubSub object or *None*.
        """
        if not self._is_connected():
            return None
        pubsub = self._client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    # ------------------------------------------------------------------
    # Streams (Redis Streams)
    # ------------------------------------------------------------------

    async def xadd(
        self,
        stream: str,
        fields: dict[str, Any],
        max_len: Optional[int] = None,
    ) -> Optional[str]:
        """Append an entry to a Redis stream.

        Args:
            stream: Stream key.
            fields: Field dict to append.
            max_len: Optional max length of the stream (approximate).

        Returns:
            Entry ID string or *None* on failure.
        """
        if not self._is_connected():
            return None
        serialized = {k: self._serialize(v) for k, v in fields.items()}
        kwargs: dict[str, Any] = {}
        if max_len:
            kwargs["maxlen"] = max_len
            kwargs["approximate"] = True
        return await self._client.xadd(stream, serialized, **kwargs)

    async def xread(
        self,
        stream: str,
        last_id: str = "0",
        count: int = 100,
    ) -> list[dict]:
        """Read entries from a Redis stream.

        Args:
            stream: Stream key.
            last_id: Read entries after this ID.
            count: Maximum number of entries to return.

        Returns:
            List of ``{id, fields}`` dicts.
        """
        if not self._is_connected():
            return []
        raw = await self._client.xread({stream: last_id}, count=count)
        results: list[dict] = []
        for _stream_name, entries in raw:
            for entry_id, entry_fields in entries:
                results.append(
                    {
                        "id": entry_id,
                        "fields": {
                            k: self._deserialize(v)
                            for k, v in entry_fields.items()
                        },
                    }
                )
        return results


# ------------------------------------------------------------------
# Caching decorator
# ------------------------------------------------------------------


def cache(ttl: int = 300, key_prefix: str = "cache"):
    """Decorator that caches the return value of an async function in Redis.

    Args:
        ttl: Cache TTL in seconds.
        key_prefix: Prefix to prepend to the cache key.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = f"{key_prefix}:{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            await redis_client.set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator


# Module-level singleton
redis_client = RedisClient()
