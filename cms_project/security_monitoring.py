"""
Security Monitoring and Alerting System
Monitors security events and generates alerts for suspicious activities.
"""

import logging
import time
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('security')


class SecurityMonitor:
    """
    Monitors security events and detects suspicious patterns.
    """
    
    @staticmethod
    def log_security_event(event_type, request, details=None, user=None):
        """
        Log a security event with context.
        
        Args:
            event_type: Type of security event (e.g., 'failed_login', 'brute_force', 'xss_attempt')
            request: Django request object
            details: Additional details about the event
            user: User associated with the event (if any)
        """
        if details is None:
            details = {}
        
        # Extract request information
        ip_address = SecurityMonitor._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        path = request.path
        method = request.method
        
        # Prepare log data
        log_data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent[:255],
            'path': path,
            'method': method,
            'user_id': user.id if user else None,
            'username': user.username if user else None,
            'details': details,
        }
        
        # Log to security logger
        logger.warning(
            f"Security event: {event_type}",
            extra={
                'ip': ip_address,
                'user': user.username if user else 'anonymous',
                'action': event_type,
                'details': details,
            }
        )
        
        # Store in cache for rate limiting and pattern detection
        SecurityMonitor._store_event_for_analysis(event_type, ip_address, user)
        
        # Check for suspicious patterns
        SecurityMonitor._check_suspicious_patterns(event_type, ip_address, user)
        
        return log_data
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    @staticmethod
    def _store_event_for_analysis(event_type, ip_address, user):
        """Store event in cache for pattern analysis."""
        # Store event by IP
        ip_key = f'security_events_ip_{ip_address}'
        ip_events = cache.get(ip_key, [])
        ip_events.append({
            'event_type': event_type,
            'timestamp': time.time(),
            'user_id': user.id if user else None,
        })
        # Keep only last 100 events
        if len(ip_events) > 100:
            ip_events = ip_events[-100:]
        cache.set(ip_key, ip_events, timeout=3600)  # 1 hour
        
        # Store event by user (if authenticated)
        if user:
            user_key = f'security_events_user_{user.id}'
            user_events = cache.get(user_key, [])
            user_events.append({
                'event_type': event_type,
                'timestamp': time.time(),
                'ip_address': ip_address,
            })
            # Keep only last 50 events
            if len(user_events) > 50:
                user_events = user_events[-50:]
            cache.set(user_key, user_events, timeout=3600)  # 1 hour
    
    @staticmethod
    def _check_suspicious_patterns(event_type, ip_address, user):
        """Check for suspicious patterns and trigger alerts."""
        
        # Check for brute force patterns
        if event_type in ['failed_login', 'invalid_credentials']:
            SecurityMonitor._check_brute_force_patterns(ip_address, user)
        
        # Check for scanning patterns
        if event_type in ['path_traversal', 'sql_injection_attempt', 'xss_attempt']:
            SecurityMonitor._check_attack_patterns(ip_address)
        
        # Check for account takeover patterns
        if event_type in ['password_change', 'email_change', 'permission_change']:
            SecurityMonitor._check_account_takeover_patterns(user, ip_address)
    
    @staticmethod
    def _check_brute_force_patterns(ip_address, user):
        """Check for brute force attack patterns."""
        ip_key = f'security_events_ip_{ip_address}'
        events = cache.get(ip_key, [])
        
        # Count failed login attempts in last 5 minutes
        recent_events = [
            e for e in events 
            if e['event_type'] in ['failed_login', 'invalid_credentials'] 
            and time.time() - e['timestamp'] < 300  # 5 minutes
        ]
        
        if len(recent_events) >= 10:  # 10 failed attempts in 5 minutes
            logger.critical(
                f"Potential brute force attack detected from IP: {ip_address}",
                extra={
                    'ip': ip_address,
                    'user': 'multiple' if not user else user.username,
                    'action': 'brute_force_detected',
                    'attempts': len(recent_events),
                }
            )
            
            # Block IP temporarily
            block_key = f'ip_blocked_{ip_address}'
            cache.set(block_key, True, timeout=1800)  # 30 minutes
    
    @staticmethod
    def _check_attack_patterns(ip_address):
        """Check for attack patterns like scanning."""
        ip_key = f'security_events_ip_{ip_address}'
        events = cache.get(ip_key, [])
        
        # Count various attack attempts in last 10 minutes
        attack_events = [
            e for e in events 
            if e['event_type'] in ['path_traversal', 'sql_injection_attempt', 'xss_attempt', 'csrf_violation']
            and time.time() - e['timestamp'] < 600  # 10 minutes
        ]
        
        if len(attack_events) >= 5:  # 5 attack attempts in 10 minutes
            logger.critical(
                f"Potential attack scanning detected from IP: {ip_address}",
                extra={
                    'ip': ip_address,
                    'user': 'attacker',
                    'action': 'attack_scanning_detected',
                    'attempts': len(attack_events),
                }
            )
    
    @staticmethod
    def _check_account_takeover_patterns(user, ip_address):
        """Check for account takeover patterns."""
        if not user:
            return
        
        user_key = f'security_events_user_{user.id}'
        events = cache.get(user_key, [])
        
        # Check for suspicious activity from new IP
        recent_events = [
            e for e in events 
            if time.time() - e['timestamp'] < 3600  # 1 hour
        ]
        
        if recent_events:
            # Get unique IPs in last hour
            unique_ips = set(e['ip_address'] for e in recent_events)
            
            if len(unique_ips) > 3:  # Activity from more than 3 IPs in 1 hour
                logger.warning(
                    f"Suspicious account activity for user {user.username} from multiple IPs",
                    extra={
                        'ip': ip_address,
                        'user': user.username,
                        'action': 'suspicious_account_activity',
                        'unique_ips': len(unique_ips),
                    }
                )


class SecurityAlert:
    """
    Handles security alerts and notifications.
    """
    
    @staticmethod
    def send_alert(alert_type, severity, message, context=None):
        """
        Send a security alert.
        
        Args:
            alert_type: Type of alert (e.g., 'brute_force', 'data_breach', 'system_compromise')
            severity: Severity level ('low', 'medium', 'high', 'critical')
            message: Alert message
            context: Additional context data
        """
        if context is None:
            context = {}
        
        alert_data = {
            'type': alert_type,
            'severity': severity,
            'message': message,
            'timestamp': timezone.now().isoformat(),
            'context': context,
        }
        
        # Log the alert
        logger.critical(
            f"SECURITY ALERT: {alert_type} - {message}",
            extra={
                'ip': context.get('ip_address', 'system'),
                'user': context.get('username', 'system'),
                'action': f'alert_{alert_type}',
                'severity': severity,
            }
        )
        
        # Store alert in cache for dashboard display
        alerts_key = 'security_alerts_recent'
        recent_alerts = cache.get(alerts_key, [])
        recent_alerts.append(alert_data)
        
        # Keep only last 50 alerts
        if len(recent_alerts) > 50:
            recent_alerts = recent_alerts[-50:]
        
        cache.set(alerts_key, recent_alerts, timeout=86400)  # 24 hours
        
        # TODO: Implement actual alerting mechanisms:
        # - Email notifications to admins
        # - Slack/Teams webhook integration
        # - SMS alerts for critical issues
        # - SIEM integration
        
        return alert_data
    
    @staticmethod
    def get_recent_alerts(limit=20):
        """Get recent security alerts."""
        alerts_key = 'security_alerts_recent'
        return cache.get(alerts_key, [])[-limit:]
    
    @staticmethod
    def get_security_metrics():
        """Get security metrics for dashboard."""
        # This would typically query the database or cache for metrics
        # For now, return placeholder metrics
        return {
            'failed_logins_24h': cache.get('metric_failed_logins_24h', 0),
            'blocked_ips_24h': cache.get('metric_blocked_ips_24h', 0),
            'xss_attempts_24h': cache.get('metric_xss_attempts_24h', 0),
            'sql_injection_attempts_24h': cache.get('metric_sql_injection_attempts_24h', 0),
            'active_threats': cache.get('metric_active_threats', 0),
        }


# Security event types for consistent logging
SECURITY_EVENTS = {
    'FAILED_LOGIN': 'failed_login',
    'SUCCESSFUL_LOGIN': 'successful_login',
    'LOGOUT': 'logout',
    'PASSWORD_CHANGE': 'password_change',
    'PERMISSION_CHANGE': 'permission_change',
    'USER_CREATE': 'user_create',
    'USER_DELETE': 'user_delete',
    'DATA_EXPORT': 'data_export',
    'DATA_IMPORT': 'data_import',
    'SQL_INJECTION_ATTEMPT': 'sql_injection_attempt',
    'XSS_ATTEMPT': 'xss_attempt',
    'PATH_TRAVERSAL': 'path_traversal',
    'CSRF_VIOLATION': 'csrf_violation',
    'RATE_LIMIT_EXCEEDED': 'rate_limit_exceeded',
    'BRUTE_FORCE_ATTEMPT': 'brute_force_attempt',
    'UNAUTHORIZED_ACCESS': 'unauthorized_access',
    'SENSITIVE_DATA_ACCESS': 'sensitive_data_access',
    'SYSTEM_CONFIG_CHANGE': 'system_config_change',
}