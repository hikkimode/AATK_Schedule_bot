"""
Caching service for schedule data using TTLCache.
"""

from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from cachetools import TTLCache
from loguru import logger

# Type variables for decorator
P = ParamSpec("P")
T = TypeVar("T")

# Global cache instances
_schedule_cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes
_user_cache = TTLCache(maxsize=200, ttl=600)  # 10 minutes
_group_cache = TTLCache(maxsize=50, ttl=1800)  # 30 minutes


def cached_schedule(ttl: int = 300, key_func: Callable | None = None):
    """
    Decorator for caching schedule queries.
    
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_func: Optional function to generate cache key
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        cache = TTLCache(maxsize=100, ttl=ttl)
        
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key: function_name:args:kwargs
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            if cache_key in cache:
                logger.debug(f"Cache hit for {cache_key}")
                return cache[cache_key]
            
            # Execute function
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache (only if result is not None)
            if result is not None:
                cache[cache_key] = result
            
            return result
        
        # Attach cache control methods
        wrapper.cache = cache
        wrapper.invalidate = lambda: cache.clear()
        
        return wrapper
    return decorator


def invalidate_schedule_cache(group_name: str | None = None):
    """
    Invalidate schedule cache.
    
    Args:
        group_name: If provided, invalidate only this group's cache.
                   If None, invalidate all schedule cache.
    """
    global _schedule_cache
    
    if group_name:
        # Invalidate specific group entries
        keys_to_remove = [
            key for key in _schedule_cache 
            if group_name in str(key)
        ]
        for key in keys_to_remove:
            del _schedule_cache[key]
        logger.info(f"Invalidated cache for group: {group_name}")
    else:
        # Clear all schedule cache
        _schedule_cache.clear()
        logger.info("Invalidated all schedule cache")


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics for monitoring."""
    return {
        "schedule_cache": {
            "size": len(_schedule_cache),
            "maxsize": _schedule_cache.maxsize,
            "currsize": _schedule_cache.currsize,
            "ttl": _schedule_cache.ttl,
        },
        "user_cache": {
            "size": len(_user_cache),
            "maxsize": _user_cache.maxsize,
            "currsize": _user_cache.currsize,
        },
        "group_cache": {
            "size": len(_group_cache),
            "maxsize": _group_cache.maxsize,
        }
    }


class CacheManager:
    """Manager for cache operations."""
    
    @staticmethod
    def get(group_name: str, day: str | None = None) -> Any | None:
        """Get cached schedule data."""
        key = f"schedule:{group_name}:{day or 'all'}"
        return _schedule_cache.get(key)
    
    @staticmethod
    def set(group_name: str, data: Any, day: str | None = None, ttl: int = 300):
        """Cache schedule data."""
        key = f"schedule:{group_name}:{day or 'all'}"
        _schedule_cache[key] = data
        logger.debug(f"Cached schedule for {key}")
    
    @staticmethod
    def delete(group_name: str, day: str | None = None):
        """Delete cached schedule data."""
        key = f"schedule:{group_name}:{day or 'all'}"
        if key in _schedule_cache:
            del _schedule_cache[key]
    
    @staticmethod
    def clear_all():
        """Clear all caches."""
        _schedule_cache.clear()
        _user_cache.clear()
        _group_cache.clear()
        logger.info("All caches cleared")


# Singleton instance
cache_manager = CacheManager()
