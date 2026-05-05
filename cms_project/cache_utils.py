"""
Cache utilities for the CMS project.
Provides enhanced cache key generation, cache management, and monitoring.
"""

import hashlib
import json
import time
import logging
from typing import Any, Dict, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


def make_cache_key(key: str, key_prefix: str = "", version: Optional[int] = None) -> str:
    """
    Generate a consistent cache key with versioning and environment prefix.
    
    Args:
        key: The base cache key
        key_prefix: Optional Django cache key prefix
        version: Optional version number for cache invalidation
        
    Returns:
        Formatted cache key with prefix and version
    """
    # Add environment prefix (development, staging, production)
    env_prefix = "dev" if settings.DEBUG else "prod"
    
    key_parts = [env_prefix]
    if key_prefix:
        key_parts.append(str(key_prefix))
    key_parts.append(str(key))
    if version is not None:
        key_parts.append(f"v{version}")

    return ":".join(key_parts)


def generate_request_cache_key(request, prefix: str = "view") -> str:
    """
    Generate a cache key based on request parameters.
    
    Args:
        request: Django HttpRequest object
        prefix: Cache key prefix
        
    Returns:
        Unique cache key for the request
    """
    # Get request parameters that affect the response
    params = {
        'path': request.path,
        'method': request.method,
        'user': str(request.user.pk) if request.user.is_authenticated else 'anonymous',
        'query': dict(request.GET),
        'accept': request.META.get('HTTP_ACCEPT', ''),
    }
    
    # Create a hash of the parameters
    params_str = json.dumps(params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
    
    return make_cache_key(f"{prefix}:{params_hash}")


def cache_get_or_set(key: str, func, timeout: Optional[int] = None, 
                     version: Optional[int] = None, **kwargs) -> Any:
    """
    Get value from cache or set it if not present.
    
    Args:
        key: Cache key
        func: Function to call if cache miss
        timeout: Cache timeout in seconds (defaults to settings.CACHES['default']['TIMEOUT'])
        version: Cache version
        **kwargs: Arguments to pass to func
        
    Returns:
        Cached or freshly computed value
    """
    # Generate full cache key
    full_key = make_cache_key(key, version=version)
    
    # Try to get from cache
    cached_value = cache.get(full_key)
    if cached_value is not None:
        logger.debug(f"Cache hit for key: {full_key}")
        return cached_value
    
    # Cache miss - compute value
    logger.debug(f"Cache miss for key: {full_key}")
    value = func(**kwargs) if kwargs else func()
    
    # Store in cache
    cache_timeout = timeout or settings.CACHES['default'].get('TIMEOUT', 300)
    cache.set(full_key, value, cache_timeout)
    
    return value


def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate cache keys matching a pattern.
    
    Args:
        pattern: Pattern to match (supports wildcards in Redis)
        
    Returns:
        Number of keys invalidated
    """
    try:
        # This requires Redis with keys command enabled
        from django_redis import get_redis_connection
        
        redis_client = get_redis_connection("default")
        
        # Use SCAN for production safety (not KEYS)
        keys = []
        cursor = 0
        while True:
            cursor, found_keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
            keys.extend(found_keys)
            if cursor == 0:
                break
        
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {pattern}")
            return len(keys)
        
    except (ImportError, AttributeError):
        # Fallback for non-Redis cache backends
        logger.warning(f"Pattern-based cache invalidation not supported for current cache backend")
    
    return 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics and health information.
    
    Returns:
        Dictionary with cache statistics
    """
    stats = {
        'backend': settings.CACHES['default']['BACKEND'],
        'timeout': settings.CACHES['default'].get('TIMEOUT', 'N/A'),
        'enabled': True,
    }
    
    try:
        # Test cache connection
        test_key = 'cache_health_test'
        test_value = 'ok'
        
        cache.set(test_key, test_value, 10)
        retrieved = cache.get(test_key)
        
        stats['connection'] = retrieved == test_value
        stats['latency'] = 'N/A'  # Could be measured with time
        
        # Get Redis-specific stats if available
        if 'redis' in stats['backend'].lower():
            from django_redis import get_redis_connection
            redis_client = get_redis_connection("default")
            
            try:
                info = redis_client.info()
                stats['redis_version'] = info.get('redis_version', 'N/A')
                stats['used_memory'] = info.get('used_memory_human', 'N/A')
                stats['connected_clients'] = info.get('connected_clients', 'N/A')
            except:
                stats['redis_info'] = 'unavailable'
                
    except Exception as e:
        stats['connection'] = False
        stats['error'] = str(e)
    
    return stats


def clear_all_cache() -> bool:
    """
    Clear all cache entries.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cache.clear()
        logger.info("Cleared all cache entries")
        return True
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return False


def warm_cache(patterns: list = None) -> Dict[str, int]:
    """
    Warm cache by preloading frequently accessed data.
    
    Args:
        patterns: List of cache key patterns to warm
        
    Returns:
        Dictionary with warming statistics
    """
    from tickets.models import Ticket, UserProfile
    
    stats = {
        'tickets_warmed': 0,
        'users_warmed': 0,
        'total_items': 0
    }
    
    try:
        # Warm recent tickets (last 100)
        recent_tickets = Ticket.objects.all().order_by('-created_at')[:100]
        for ticket in recent_tickets:
            key = f"ticket:{ticket.id}"
            cache.set(key, {
                'id': ticket.id,
                'title': ticket.title,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat()
            }, timeout=3600)  # 1 hour
            stats['tickets_warmed'] += 1
        
        # Warm active users
        active_users = UserProfile.objects.filter(is_active=True)[:50]
        for user in active_users:
            key = f"user:{user.id}"
            cache.set(key, {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff
            }, timeout=1800)  # 30 minutes
            stats['users_warmed'] += 1
        
        stats['total_items'] = stats['tickets_warmed'] + stats['users_warmed']
        logger.info(f"Cache warmed: {stats['total_items']} items")
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
    
    return stats


def cache_with_fallback(key: str, func, fallback_func=None,
                       timeout: int = 300, version: Optional[int] = None) -> Any:
    """
    Get from cache, compute if missing, with fallback on error.
    
    Args:
        key: Cache key
        func: Primary function to compute value
        fallback_func: Fallback function if primary fails
        timeout: Cache timeout
        version: Cache version
        
    Returns:
        Cached value or computed/fallback value
    """
    full_key = make_cache_key(key, version=version)
    
    # Try cache first
    cached = cache.get(full_key)
    if cached is not None:
        return cached
    
    # Try primary function
    try:
        value = func()
        cache.set(full_key, value, timeout)
        return value
    except Exception as e:
        logger.warning(f"Primary function failed for {key}: {e}")
        
        # Try fallback
        if fallback_func:
            try:
                value = fallback_func()
                cache.set(full_key, value, timeout // 2)  # Shorter timeout for fallback
                return value
            except Exception as e2:
                logger.error(f"Fallback also failed for {key}: {e2}")
        
        # Return None or raise based on context
        return None


def get_cache_metrics() -> Dict[str, Any]:
    """
    Get detailed cache performance metrics.
    
    Returns:
        Dictionary with hit rates, memory usage, etc.
    """
    metrics = {
        'hits': 0,
        'misses': 0,
        'hit_rate': 0.0,
        'size': 0,
        'keys': 0
    }
    
    try:
        if 'redis' in settings.CACHES['default']['BACKEND'].lower():
            from django_redis import get_redis_connection
            import time
            
            redis_client = get_redis_connection("default")
            
            # Get Redis info
            info = redis_client.info()
            
            # Calculate approximate hit rate from Redis stats
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            
            metrics['hits'] = hits
            metrics['misses'] = misses
            metrics['hit_rate'] = hits / total if total > 0 else 0.0
            metrics['size'] = info.get('used_memory', 0)
            metrics['keys'] = info.get('db0', {}).get('keys', 0) if 'db0' in info else 0
            
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}")
    
    return metrics


class CacheMiddleware:
    """
    Middleware to add cache headers and monitor cache performance.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Start timing for cache performance monitoring
        start_time = time.time() if 'time' in globals() else None
        
        response = self.get_response(request)
        
        # Add cache control headers for cacheable responses
        if response.status_code == 200 and request.method == 'GET':
            # Don't cache authenticated API responses by default
            if not request.user.is_authenticated:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
                response['Vary'] = 'Accept-Encoding, Cookie'
            else:
                # Shorter cache for authenticated users
                response['Cache-Control'] = 'private, max-age=60'
        
        # Add cache performance header
        if start_time and 'time' in globals():
            response['X-Cache-Performance'] = f"{time.time() - start_time:.3f}s"
        
        return response


class TieredCache:
    """
    Implements a two-tier caching strategy with fast (memory) and slow (Redis/disk) layers.
    """
    
    def __init__(self, fast_timeout=60, slow_timeout=3600):
        self.fast_timeout = fast_timeout
        self.slow_timeout = slow_timeout
        self.local_cache = {}
        self.local_cache_expiry = {}
    
    def get(self, key):
        # Check local cache first
        now = time.time()
        if key in self.local_cache:
            expiry = self.local_cache_expiry.get(key, 0)
            if now < expiry:
                return self.local_cache[key]
            else:
                # Expired, remove from local cache
                del self.local_cache[key]
                del self.local_cache_expiry[key]
        
        # Check Redis/slow cache
        value = cache.get(key)
        if value is not None:
            # Store in local cache for faster subsequent access
            self.local_cache[key] = value
            self.local_cache_expiry[key] = now + self.fast_timeout
        
        return value
    
    def set(self, key, value):
        # Set in both caches
        self.local_cache[key] = value
        self.local_cache_expiry[key] = time.time() + self.fast_timeout
        cache.set(key, value, self.slow_timeout)
    
    def delete(self, key):
        # Delete from both caches
        if key in self.local_cache:
            del self.local_cache[key]
            del self.local_cache_expiry[key]
        cache.delete(key)
