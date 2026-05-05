"""
Security hardening configurations and utilities for the CMS project.
Provides enhanced security settings, headers, and protection mechanisms.
"""

import os
import re
import logging
from django.conf import settings
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware

logger = logging.getLogger(__name__)


class EnhancedSecurityMiddleware(SecurityMiddleware):
    """
    Enhanced security middleware with additional security headers and protections.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add additional security headers
        self.add_security_headers(request, response)
        
        # Apply security policies
        self.apply_security_policies(request, response)
        
        return response
    
    def add_security_headers(self, request, response):
        """
        Add comprehensive security headers to the response.
        """
        # Content Security Policy (CSP)
        if getattr(settings, 'CSP_ENABLED', False):
            csp_directives = [
                f"default-src {self._format_csp(settings.CSP_DEFAULT_SRC)}",
                f"script-src {self._format_csp(settings.CSP_SCRIPT_SRC)}",
                f"style-src {self._format_csp(settings.CSP_STYLE_SRC)}",
                f"img-src {self._format_csp(settings.CSP_IMG_SRC)}",
                f"font-src {self._format_csp(settings.CSP_FONT_SRC)}",
                f"connect-src {self._format_csp(settings.CSP_CONNECT_SRC)}",
                f"frame-src {self._format_csp(settings.CSP_FRAME_SRC)}",
                f"media-src {self._format_csp(settings.CSP_MEDIA_SRC)}",
                f"object-src 'none'",  # Disallow plugins
                f"base-uri 'self'",
                f"form-action 'self'",
                f"frame-ancestors 'none'",  # Replace X-Frame-Options
                f"block-all-mixed-content",
                f"upgrade-insecure-requests" if not settings.DEBUG else "",
            ]
            
            # Filter out empty directives
            csp_directives = [d for d in csp_directives if d and not d.endswith(" ")]
            response['Content-Security-Policy'] = "; ".join(csp_directives)
        
        # Additional security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': (
                'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
                'magnetometer=(), microphone=(), payment=(), usb=()'
            ),
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
            'Cross-Origin-Embedder-Policy': 'require-corp',
        }
        
        # Add headers if not already present
        for header, value in security_headers.items():
            if header not in response:
                response[header] = value
        
        # Add security headers for API responses
        if request.path.startswith('/api/') or request.path.startswith('/panel/api/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
    
    def _format_csp(self, sources):
        """
        Format CSP sources for header.
        """
        if isinstance(sources, (list, tuple)):
            return " ".join(sources)
        return sources
    
    def apply_security_policies(self, request, response):
        """
        Apply additional security policies.
        """
        # Rate limiting tracking
        if hasattr(request, 'rate_limit_key'):
            response['X-RateLimit-Limit'] = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60)
            response['X-RateLimit-Remaining'] = getattr(request, 'rate_limit_remaining', 60)
            response['X-RateLimit-Reset'] = getattr(request, 'rate_limit_reset', 60)
        
        # Security event logging for sensitive actions
        self.log_security_event(request, response)
    
    def log_security_event(self, request, response):
        """
        Log security-relevant events.
        """
        # Log authentication events
        if request.path in ['/panel/login/', '/panel/logout/', '/admin/login/']:
            user = getattr(request, 'user', None)
            username = user if getattr(user, 'is_authenticated', False) else 'anonymous'
            logger.info(
                f"Security event: {request.method} {request.path} - "
                f"User: {username} - "
                f"IP: {self.get_client_ip(request)} - "
                f"Status: {response.status_code}"
            )
        
        # Log high-risk actions
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            if response.status_code >= 400:
                logger.warning(
                    f"Failed security-sensitive request: {request.method} {request.path} - "
                    f"Status: {response.status_code} - "
                    f"IP: {self.get_client_ip(request)}"
                )
    
    def get_client_ip(self, request):
        """
        Get client IP address considering proxies.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityConfiguration:
    """
    Centralized security configuration management.
    """
    
    @staticmethod
    def get_security_settings():
        """
        Get comprehensive security settings.
        """
        return {
            'password_policy': {
                'min_length': 12,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_special_chars': True,
                'max_age_days': 90,
                'history_size': 5,
            },
            'session_security': {
                'cookie_secure': not settings.DEBUG,
                'cookie_httponly': True,
                'cookie_samesite': 'Lax',
                'session_timeout': 1209600,  # 2 weeks
                'absolute_timeout': 2592000,  # 30 days
                'renewal_threshold': 604800,  # 7 days
            },
            'rate_limiting': {
                'enabled': True,
                'anonymous_per_minute': 60,
                'authenticated_per_minute': 120,
                'api_per_minute': 100,
                'burst_factor': 1.5,
            },
            'brute_force_protection': {
                'max_attempts': 5,
                'lockout_duration': 3600,  # 1 hour
                'reset_on_success': True,
            },
            'csp_config': {
                'enabled': not settings.DEBUG,
                'report_only': False,
                'report_uri': '/csp-violation-report/',
            },
            'headers': {
                'hsts_max_age': 31536000,  # 1 year
                'hsts_include_subdomains': True,
                'hsts_preload': True,
            },
        }
    
    @staticmethod
    def validate_security_configuration():
        """
        Validate current security configuration and report issues.
        """
        issues = []
        
        # Check DEBUG mode
        if settings.DEBUG:
            issues.append("DEBUG mode is enabled - security headers may be weakened")
        
        # Check secret key
        if settings.SECRET_KEY == 'django-insecure-default-key':
            issues.append("Default SECRET_KEY detected - change in production")
        
        # Check allowed hosts
        if '*' in settings.ALLOWED_HOSTS and not settings.DEBUG:
            issues.append("ALLOWED_HOSTS contains '*' - this is insecure in production")
        
        # Check SSL settings
        if not settings.DEBUG:
            if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
                issues.append("SECURE_SSL_REDIRECT is disabled")
            if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
                issues.append("SESSION_COOKIE_SECURE is disabled")
            if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
                issues.append("CSRF_COOKIE_SECURE is disabled")
        
        return issues
    
    @staticmethod
    def generate_security_report():
        """
        Generate a comprehensive security report.
        """
        config = SecurityConfiguration.get_security_settings()
        issues = SecurityConfiguration.validate_security_configuration()
        
        report = {
            'timestamp': os.path.getmtime(__file__),
            'security_configuration': config,
            'validation_issues': issues,
            'recommendations': SecurityConfiguration.get_security_recommendations(),
            'environment': {
                'debug': settings.DEBUG,
                'allowed_hosts': settings.ALLOWED_HOSTS,
                'ssl_redirect': getattr(settings, 'SECURE_SSL_REDIRECT', 'Not set'),
                'hsts_enabled': getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0,
            }
        }
        
        return report
    
    @staticmethod
    def get_security_recommendations():
        """
        Get security improvement recommendations.
        """
        recommendations = []
        
        if not getattr(settings, 'CSP_ENABLED', False):
            recommendations.append("Enable Content Security Policy (CSP)")
        
        if not getattr(settings, 'SECURE_BROWSER_XSS_FILTER', False):
            recommendations.append("Enable XSS filter with 'X-XSS-Protection: 1; mode=block'")
        
        if not getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False):
            recommendations.append("Enable content type nosniffing")
        
        if getattr(settings, 'SESSION_COOKIE_AGE', 1209600) > 1209600:  # 2 weeks
            recommendations.append("Consider reducing session cookie age")
        
        return recommendations


class SecurityAuditLogger:
    """
    Log security events for auditing and monitoring.
    """
    
    @staticmethod
    def log_event(event_type, request, details=None):
        """
        Log a security event.
        """
        event_data = {
            'event_type': event_type,
            'timestamp': os.path.getmtime(__file__),
            'ip_address': SecurityAuditLogger.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
            'user': str(request.user) if getattr(getattr(request, 'user', None), 'is_authenticated', False) else 'anonymous',
            'method': request.method,
            'path': request.path,
            'details': details or {},
        }
        
        # Log to security log file
        logger.info(f"Security audit event: {event_data}")
        
        # Could also send to external monitoring system
        SecurityAuditLogger.send_to_monitoring(event_data)
    
    @staticmethod
    def get_client_ip(request):
        """
        Get client IP address.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def send_to_monitoring(event_data):
        """
        Send event to external monitoring system (placeholder).
        """
        # In a real implementation, this would send to SIEM, Splunk, etc.
        pass


# Security event types
SECURITY_EVENTS = {
    'LOGIN_SUCCESS': 'user_login_success',
    'LOGIN_FAILURE': 'user_login_failure',
    'LOGOUT': 'user_logout',
    'PASSWORD_CHANGE': 'password_change',
    'PERMISSION_DENIED': 'permission_denied',
    'RATE_LIMIT_EXCEEDED': 'rate_limit_exceeded',
    'SUSPICIOUS_ACTIVITY': 'suspicious_activity',
    'FILE_UPLOAD': 'file_upload',
    'DATA_EXPORT': 'data_export',
    'CONFIGURATION_CHANGE': 'configuration_change',
}
