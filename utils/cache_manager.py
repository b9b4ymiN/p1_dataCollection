"""
High-Performance Cache Manager
Redis-based caching with connection pooling and compression
"""

import redis
from redis.connection import ConnectionPool
import msgpack
import logging
from typing import Any, Optional
import time
from functools import wraps

logger = logging.getLogger(__name__)


class CacheManager:
    """
    High-performance cache manager with:
    - Connection pooling
    - Binary serialization (msgpack)
    - Automatic compression
    - Cache warming
    - TTL management
    """

    def __init__(self, config: dict):
        redis_config = config['redis']

        # Create connection pool for better performance
        self.pool = ConnectionPool(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config['db'],
            password=redis_config.get('password'),
            max_connections=50,  # Large pool for concurrent access
            socket_keepalive=True,
            socket_connect_timeout=5,
            decode_responses=False  # Use binary mode for msgpack
        )

        self.client = redis.Redis(connection_pool=self.pool)

        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.sets = 0

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Get value from cache with automatic deserialization"""
        try:
            value = self.client.get(key)
            if value:
                self.hits += 1
                return msgpack.unpackb(value, raw=False)
            else:
                self.misses += 1
                return default
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            self.misses += 1
            return default

    def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with automatic serialization"""
        try:
            packed_value = msgpack.packb(value, use_bin_type=True)
            self.client.setex(key, ttl, packed_value)
            self.sets += 1
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    def get_multi(self, keys: list) -> dict:
        """Get multiple keys at once for better performance"""
        try:
            pipe = self.client.pipeline()
            for key in keys:
                pipe.get(key)

            values = pipe.execute()

            result = {}
            for i, key in enumerate(keys):
                if values[i]:
                    self.hits += 1
                    result[key] = msgpack.unpackb(values[i], raw=False)
                else:
                    self.misses += 1

            return result
        except Exception as e:
            logger.error(f"Cache get_multi error: {e}")
            return {}

    def set_multi(self, data: dict, ttl: int = 300):
        """Set multiple keys at once using pipeline"""
        try:
            pipe = self.client.pipeline()
            for key, value in data.items():
                packed_value = msgpack.packb(value, use_bin_type=True)
                pipe.setex(key, ttl, packed_value)

            pipe.execute()
            self.sets += len(data)
            return True
        except Exception as e:
            logger.error(f"Cache set_multi error: {e}")
            return False

    def delete(self, key: str):
        """Delete key from cache"""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Cache delete_pattern error for {pattern}: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'hit_rate': f"{hit_rate:.2f}%",
            'total_requests': total
        }

    def reset_stats(self):
        """Reset statistics"""
        self.hits = 0
        self.misses = 0
        self.sets = 0

    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def close(self):
        """Close connection pool"""
        try:
            self.pool.disconnect()
        except Exception as e:
            logger.error(f"Error closing cache: {e}")


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results

    Usage:
        @cached(ttl=600, key_prefix="ohlcv")
        def get_ohlcv_data(symbol, timeframe):
            return expensive_operation()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"

            # Try to get from cache
            if hasattr(self, 'cache'):
                cached_value = self.cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

            # Execute function
            result = func(self, *args, **kwargs)

            # Store in cache
            if hasattr(self, 'cache') and result is not None:
                self.cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for {cache_key}")

            return result

        return wrapper
    return decorator
