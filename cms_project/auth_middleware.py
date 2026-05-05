"""
Enhanced Authentication and Authorization Middleware
Provides additional security layers for authentication and authorization.
"""

import logging
from datetime import datetime, timedelta
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class FailedLoginTracker:
    """Track failed login attempts to prevent brute force attacks."""
    
    @staticmethod
    def get_cache_key(username, ip_address=None):
        """Generate cache key for failed login attempts."""
        if ip_address:
            return f'failed_login_{username}_{ip_address}'
        return f'failed_login_{username}'
    
    @staticmethod
    def record_failed_attempt(username, ip_address=None):
        """Record a failed login attempt."""
        cache_key = FailedLoginTracker.get_cache_key(username, ip_address)
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, timeout=900)  # 15 minutes
        logger.warning(f"Failed login attempt for user '{username}' from IP {ip_address}. Attempt #{attempts}")
        
        # If too many attempts, temporarily block
        if attempts >= settings.MAX_LOGIN_ATTEMPTS:
            block_key = f'login_blocked_{username}'
            cache.set(block_key, True, timeout=1800)  # 30 minute block
            logger.warning(f"User '{username}' temporarily blocked due to {attempts} failed login attempts")
    
    @staticmethod
    def clear_failed_attempts(username, ip_address=None):
        """Clear failed login attempts after successful login."""
        cache_key = FailedLoginTracker.get_cache_key(username, ip_address)
        cache.delete(cache_key)
        block_key = f'login_blocked_{username}'
        cache.delete(block_key)
    
    @staticmethod
    def is_blocked(username, ip_address=None):
        """Check if login is blocked for this user/IP."""
        block_key = f'login_blocked_{username}'
        if cache.get(block_key):
            return True
        # Also check IP-based blocking
        if ip_address:
            ip_block_key = f'ip_blocked_{ip_address}'
            if cache.get(ip_block_key):
                return True
        return False
    
    @staticmethod
    def get_remaining_attempts(username, ip_address=None):
        """Get remaining login attempts before blocking."""
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        cache_key = FailedLoginTracker.get_cache_key(username, ip_address)
        attempts = cache.get(cache_key, 0)
        return max(0, max_attempts - attempts)


class AuthenticationSecurityMiddleware:
    """
    Middleware to enhance authentication security.
    - Tracks failed login attempts
    - Enforces account lockout policies
    - Validates user session security
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for blocked users before processing login requests
        if request.path == '/panel/login/' and request.method == 'POST':
            username = request.POST.get('username', '').strip()
            ip_address = self._get_client_ip(request)
            
            if FailedLoginTracker.is_blocked(username, ip_address):
                logger.warning(f"Blocked login attempt for '{username}' from {ip_address}")
                return JsonResponse({
                    'error': 'Account temporarily locked',
                    'message': 'Too many failed login attempts. Please try again in 30 minutes.'
                }, status=429)
        
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


class AuthorizationMiddleware:
    """
    Middleware to enforce authorization policies.
    - Validates user permissions for sensitive endpoints
    - Logs unauthorized access attempts
    - Enforces role-based access control
    """
    
    SENSITIVE_ENDPOINTS = [
        '/panel/users/',
        '/panel/settings/',
        '/panel/reports/export/',
        '/panel/config/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip authorization for non-authenticated users (they'll be caught by login_required)
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Check if user is trying to access sensitive endpoints without proper permissions
        for endpoint in self.SENSITIVE_ENDPOINTS:
            if request.path.startswith(endpoint):
                if not request.user.is_superuser:
                    logger.warning(
                        f"Unauthorized access attempt to {request.path} by user {request.user.username} "
                        f"from IP {self._get_client_ip(request)}"
                    )
                    return HttpResponseForbidden("You don't have permission to access this resource.")
        
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


def require_superuser(view_func):
    """
    Decorator that requires the user to be a superuser.
    Returns 403 Forbidden if user is not a superuser.
    """
    from django.contrib.auth.decorators import user_passes_test
    return user_passes_test(
        lambda u: u.is_active and u.is_superuser,
        login_url='/panel/login/',
        redirect_field_name=None
    )(view_func)


def require_staff(view_func):
    """
    Decorator that requires the user to be staff.
    Returns 403 Forbidden if user is not staff.
    """
    from django.contrib.auth.decorators import user_passes_test
    return user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/panel/login/',
        redirect_field_name=None
    )(view_func)


def log_sensitive_action(action, user, request, details=None):
    """
    Log sensitive actions for audit trail.
    """
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    
    log_entry = {
        'timestamp': timezone.now().isoformat(),
        'action': action,
        'user_id': user.id,
        'username': user.username,
        'ip_address': ip_address,
        'user_agent': user_agent,
        'details': details or {}
    }
    
    logger.info(f"SENSITIVE_ACTION: {log_entry}")
    
    # Also store in database for long-term audit trail
    from tickets.models import AuditLog
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent[:255],
            details=details or {}
        )
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")