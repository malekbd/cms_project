"""
Rate Limiting Middleware
Provides protection against brute force attacks and API abuse.
"""

import time
import hashlib
import logging
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseForbidden
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter implementation using Django cache.
    Supports different rate limits for different endpoints and IPs/users.
    """
    
    # Rate limit configurations (requests per time window)
    RATE_LIMITS = {
        'login': {'limit': 5, 'window': 300},  # 5 attempts per 5 minutes
        'api': {'limit': 100, 'window': 60},   # 100 requests per minute
        'export': {'limit': 10, 'window': 3600},  # 10 exports per hour
        'default': {'limit': 60, 'window': 60},  # 60 requests per minute
    }
    
    @staticmethod
    def get_client_identifier(request):
        """
        Generate a unique identifier for the client.
        Uses IP address for anonymous users, user ID for authenticated users.
        """
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        # For authenticated users, include user ID
        if request.user.is_authenticated:
            return f"user_{request.user.id}_{ip}"
        return f"ip_{ip}"
    
    @staticmethod
    def get_endpoint_category(request):
        """
        Categorize endpoints for different rate limits.
        """
        path = request.path
        
        if path.startswith('/panel/login'):
            return 'login'
        elif path.startswith('/api/'):
            return 'api'
        elif '/export' in path or path.endswith('/csv/') or path.endswith('/pdf/'):
            return 'export'
        else:
            return 'default'
    
    @staticmethod
    def is_rate_limited(request):
        """
        Check if the request should be rate limited.
        Returns (is_limited, retry_after_seconds) tuple.
        """
        # Skip rate limiting for superusers in development
        if settings.DEBUG and request.user.is_superuser:
            return False, 0
        
        client_id = RateLimiter.get_client_identifier(request)
        endpoint_category = RateLimiter.get_endpoint_category(request)
        
        # Get rate limit configuration
        limit_config = RateLimiter.RATE_LIMITS.get(endpoint_category, RateLimiter.RATE_LIMITS['default'])
        limit = limit_config['limit']
        window = limit_config['window']
        
        # Generate cache key
        cache_key = f"rate_limit_{endpoint_category}_{client_id}"
        
        # Get current request count and timestamp
        current_time = time.time()
        request_data = cache.get(cache_key, {'count': 0, 'start_time': current_time})
        
        # Reset if window has passed
        if current_time - request_data['start_time'] > window:
            request_data = {'count': 1, 'start_time': current_time}
        else:
            request_data['count'] += 1
        
        # Update cache
        cache.set(cache_key, request_data, timeout=window)
        
        # Check if limit exceeded
        if request_data['count'] > limit:
            retry_after = int(window - (current_time - request_data['start_time']))
            logger.warning(
                f"Rate limit exceeded: {client_id} made {request_data['count']} "
                f"requests to {endpoint_category} (limit: {limit}/{window}s)"
            )
            return True, retry_after
        
        return False, 0
    
    @staticmethod
    def get_remaining_requests(request):
        """
        Get remaining requests for the current client and endpoint.
        """
        client_id = RateLimiter.get_client_identifier(request)
        endpoint_category = RateLimiter.get_endpoint_category(request)
        
        limit_config = RateLimiter.RATE_LIMITS.get(endpoint_category, RateLimiter.RATE_LIMITS['default'])
        limit = limit_config['limit']
        
        cache_key = f"rate_limit_{endpoint_category}_{client_id}"
        request_data = cache.get(cache_key, {'count': 0, 'start_time': time.time()})
        
        remaining = max(0, limit - request_data['count'])
        return remaining


class RateLimitMiddleware:
    """
    Middleware to enforce rate limits on requests.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check rate limit
        is_limited, retry_after = RateLimiter.is_rate_limited(request)
        
        if is_limited:
            # Add retry-after header
            response = JsonResponse({
                'error': 'Rate limit exceeded',
                'message': f'Too many requests. Please try again in {retry_after} seconds.',
                'retry_after': retry_after
            }, status=429)
            response['Retry-After'] = str(retry_after)
            return response
        
        # Add remaining requests header for API responses
        response = self.get_response(request)
        
        if request.path.startswith('/api/') or request.path.startswith('/panel/'):
            remaining = RateLimiter.get_remaining_requests(request)
            response['X-RateLimit-Remaining'] = str(remaining)
            
            endpoint_category = RateLimiter.get_endpoint_category(request)
            limit_config = RateLimiter.RATE_LIMITS.get(endpoint_category, RateLimiter.RATE_LIMITS['default'])
            response['X-RateLimit-Limit'] = str(limit_config['limit'])
        
        return response


class BruteForceProtectionMiddleware:
    """
    Specialized middleware for brute force attack protection.
    Focuses on login endpoints and sensitive operations.
    """
    
    SENSITIVE_ENDPOINTS = [
        '/panel/login/',
        '/panel/change-password/',
        '/panel/reset-password/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check sensitive endpoints
        if any(request.path.startswith(endpoint) for endpoint in self.SENSITIVE_ENDPOINTS):
            client_ip = self._get_client_ip(request)
            
            # Check if IP is temporarily blocked
            block_key = f'bruteforce_block_{client_ip}'
            if cache.get(block_key):
                logger.warning(f"Blocked brute force attempt from IP: {client_ip}")
                return JsonResponse({
                    'error': 'Access temporarily blocked',
                    'message': 'Too many failed attempts from your IP address. Please try again later.'
                }, status=429)
            
            # Track failed attempts
            if request.method == 'POST' and request.path == '/panel/login/':
                # This will be handled by AuthenticationSecurityMiddleware
                pass
        
        response = self.get_response(request)
        return response
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip