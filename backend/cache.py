"""
Bharat Tech Atlas v4.00.02 — Production Cache Layer
Pluggable TTL+LRU cache with one-line Redis swap-in.

Features:
- Thread-safe in-memory TTLCache (default)
- Auto-detect Redis via REDIS_URL env var
- Graceful fallback if Redis unavailable
- @cached decorator for instant endpoint caching
- Global cache instances: entity, search, ml, facet

Usage:
    from backend.cache import entity_cache, get_cache
    
    # Manual get/set
    entity_cache.set("key", value, ttl=300)
    val = entity_cache.get("key")
    
    # Decorator
    from backend.cache import cached
    @cached(ttl=60, key_prefix="api")
    def my_endpoint(...): ...
    
    # Redis (one-line switch)
    export REDIS_URL="redis://localhost:6379/0"
"""
import os
import time
import threading
import hashlib
import json
import logging
from typing import Optional, Any, Callable
from functools import wraps

logger = logging.getLogger("bta.cache")

# ─── In-Memory TTL+LRU Cache ─────────────────────────────────────────────────
class TTLCache:
    """Thread-safe in-memory cache with TTL and LRU eviction."""
    
    def __init__(self, maxsize: int = 10000, default_ttl: int = 300):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._store: dict = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, v in self._store.items() if v["expires"] <= now]
        for k in expired:
            del self._store[k]
    
    def _evict_lru(self):
        if len(self._store) >= self.maxsize:
            oldest = min(self._store.items(), key=lambda x: x[1]["last_access"])
            del self._store[oldest[0]]
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            self._cleanup_expired()
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry["expires"] <= time.time():
                del self._store[key]
                self._misses += 1
                return None
            entry["last_access"] = time.time()
            self._hits += 1
            return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._cleanup_expired()
            self._evict_lru()
            expires = time.time() + (ttl or self.default_ttl)
            self._store[key] = {
                "value": value,
                "expires": expires,
                "last_access": time.time(),
            }
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False
    
    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
    
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "backend": "memory",
                "size": len(self._store),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
                "default_ttl": self.default_ttl,
            }


# ─── Redis Cache Wrapper ─────────────────────────────────────────────────────
class RedisCache:
    """Redis-backed cache with same interface as TTLCache."""
    
    def __init__(self, redis_url: str, default_ttl: int = 300):
        import redis
        self._client = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            if raw is None:
                with self._lock:
                    self._misses += 1
                return None
            with self._lock:
                self._hits += 1
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            raw = json.dumps(value, default=str)
            self._client.setex(key, ttl or self.default_ttl, raw)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
    
    def delete(self, key: str) -> bool:
        try:
            return self._client.delete(key) > 0
        except Exception:
            return False
    
    def clear(self) -> None:
        try:
            self._client.flushdb()
        except Exception as e:
            logger.warning(f"Redis clear failed: {e}")
    
    def stats(self) -> dict:
        try:
            info = self._client.info()
            return {
                "backend": "redis",
                "size": self._client.dbsize(),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / (self._hits + self._misses), 3) if (self._hits + self._misses) > 0 else 0.0,
                "default_ttl": self.default_ttl,
                "redis_version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            return {"backend": "redis", "error": str(e), "default_ttl": self.default_ttl}


# ─── Cache Factory ───────────────────────────────────────────────────────────
def get_cache(name: str = "default", maxsize: int = 10000, default_ttl: int = 300) -> Any:
    """Get or create a cache instance. Auto-detects Redis if REDIS_URL is set."""
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis  # noqa: F401
            logger.info(f"Using Redis cache for '{name}' ({redis_url})")
            return RedisCache(redis_url, default_ttl=default_ttl)
        except ImportError:
            logger.warning("redis package not installed, falling back to memory cache")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, falling back to memory cache")
    
    logger.info(f"Using in-memory TTLCache for '{name}' (maxsize={maxsize}, ttl={default_ttl})")
    return TTLCache(maxsize=maxsize, default_ttl=default_ttl)


# ─── Global Cache Instances ─────────────────────────────────────────────────
entity_cache = get_cache("entity", maxsize=50000, default_ttl=300)
search_cache = get_cache("search", maxsize=10000, default_ttl=60)
ml_cache = get_cache("ml", maxsize=5000, default_ttl=120)
facet_cache = get_cache("facet", maxsize=5000, default_ttl=300)


# ─── Decorator ──────────────────────────────────────────────────────────────
def cached(ttl: int = 60, key_prefix: str = "", key_builder: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache(func.__name__, default_ttl=ttl)
            
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Build key from args + kwargs
                sig = hashlib.sha256(
                    json.dumps({"args": args, "kwargs": kwargs}, default=str).encode()
                ).hexdigest()[:16]
                cache_key = f"{key_prefix}:{func.__name__}:{sig}"
            
            cached_val = cache.get(cache_key)
            if cached_val is not None:
                return cached_val
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator


# ─── Cache Health Check ──────────────────────────────────────────────────────
def cache_health() -> dict:
    """Return health status for all caches."""
    return {
        "entity_cache": entity_cache.stats(),
        "search_cache": search_cache.stats(),
        "ml_cache": ml_cache.stats(),
        "facet_cache": facet_cache.stats(),
    }
