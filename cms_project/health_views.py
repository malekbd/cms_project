"""
Health check and metrics views for the CMS project.
Provides endpoints for monitoring, health checks, and metrics collection.
"""

import time
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache
from django.db import connections
import logging

logger = logging.getLogger(__name__)


@require_GET
@csrf_exempt
def health_check(request):
    """
    Basic health check endpoint.
    Returns 200 OK if the application is healthy.
    """
    checks = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {},
    }
    
    # Check database connection
    try:
        conn = connections['default']
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        checks['checks']['database'] = {
            'status': 'healthy' if result and result[0] == 1 else 'unhealthy',
            'engine': conn.settings_dict['ENGINE'],
        }
    except Exception as e:
        checks['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        checks['status'] = 'unhealthy'
    
    # Check cache connection
    try:
        test_key = 'health_check'
        test_value = 'ok'
        
        cache.set(test_key, test_value, 10)
        retrieved = cache.get(test_key)
        
        checks['checks']['cache'] = {
            'status': 'healthy' if retrieved == test_value else 'unhealthy',
            'backend': settings.CACHES['default']['BACKEND'],
        }
        
        if retrieved != test_value:
            checks['status'] = 'unhealthy'
    except Exception as e:
        checks['checks']['cache'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        checks['status'] = 'unhealthy'
    
    # Check storage
    try:
        import os
        media_writable = os.access(settings.MEDIA_ROOT, os.W_OK) if hasattr(settings, 'MEDIA_ROOT') else False
        static_writable = os.access(settings.STATIC_ROOT, os.W_OK) if hasattr(settings, 'STATIC_ROOT') else False
        
        checks['checks']['storage'] = {
            'status': 'healthy' if media_writable and static_writable else 'warning',
            'media_writable': media_writable,
            'static_writable': static_writable,
        }
        
        if not (media_writable and static_writable):
            checks['status'] = 'warning'
    except Exception as e:
        checks['checks']['storage'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        checks['status'] = 'unhealthy'
    
    # Return appropriate HTTP status
    if checks['status'] == 'healthy':
        return JsonResponse(checks, status=200)
    elif checks['status'] == 'warning':
        return JsonResponse(checks, status=206)  # Partial content
    else:
        return JsonResponse(checks, status=503)  # Service unavailable


@require_GET
@csrf_exempt
def health_check_liveness(request):
    """
    Liveness probe for Kubernetes/container orchestration.
    Simple check that the application is running.
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': time.time(),
    }, status=200)


@require_GET
@csrf_exempt
def health_check_readiness(request):
    """
    Readiness probe for Kubernetes/container orchestration.
    Checks if the application is ready to serve traffic.
    """
    checks = {
        'status': 'ready',
        'timestamp': time.time(),
        'checks': {},
    }
    
    # Check database
    try:
        conn = connections['default']
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        checks['checks']['database'] = {'status': 'ready'}
    except Exception as e:
        checks['checks']['database'] = {'status': 'not_ready', 'error': str(e)}
        checks['status'] = 'not_ready'
    
    # Check cache
    try:
        cache.set('readiness_check', 'ok', 5)
        checks['checks']['cache'] = {'status': 'ready'}
    except Exception as e:
        checks['checks']['cache'] = {'status': 'not_ready', 'error': str(e)}
        checks['status'] = 'not_ready'
    
    status_code = 200 if checks['status'] == 'ready' else 503
    return JsonResponse(checks, status=status_code)


@require_GET
@csrf_exempt
def metrics(request):
    """
    Application metrics endpoint (Prometheus format).
    """
    from cms_project.monitoring_utils import get_comprehensive_metrics
    
    try:
        metrics_data = get_comprehensive_metrics()
        
        # Convert to Prometheus format
        prometheus_lines = []
        
        # System metrics
        system = metrics_data.get('system', {})
        if system and 'error' not in system:
            prometheus_lines.append(f"# HELP system_cpu_percent CPU usage percentage")
            prometheus_lines.append(f"# TYPE system_cpu_percent gauge")
            prometheus_lines.append(f'system_cpu_percent{{component="cms"}} {system.get("cpu", {}).get("percent", 0)}')
            
            prometheus_lines.append(f"# HELP system_memory_percent Memory usage percentage")
            prometheus_lines.append(f"# TYPE system_memory_percent gauge")
            prometheus_lines.append(f'system_memory_percent{{component="cms"}} {system.get("memory", {}).get("percent", 0)}')
            
            prometheus_lines.append(f"# HELP system_disk_percent Disk usage percentage")
            prometheus_lines.append(f"# TYPE system_disk_percent gauge")
            prometheus_lines.append(f'system_disk_percent{{component="cms"}} {system.get("disk", {}).get("percent", 0)}')
        
        # Application metrics
        app = metrics_data.get('application', {})
        if app:
            total_requests = app.get('requests', {}).get('total', 0)
            prometheus_lines.append(f"# HELP app_requests_total Total requests")
            prometheus_lines.append(f"# TYPE app_requests_total counter")
            prometheus_lines.append(f'app_requests_total{{component="cms"}} {total_requests}')
            
            error_count = sum(app.get('errors', {}).values())
            prometheus_lines.append(f"# HELP app_errors_total Total errors")
            prometheus_lines.append(f"# TYPE app_errors_total counter")
            prometheus_lines.append(f'app_errors_total{{component="cms"}} {error_count}')
        
        # Health status
        health = metrics_data.get('health', {})
        health_status = 1 if health.get('status') == 'healthy' else 0
        prometheus_lines.append(f"# HELP app_health_status Application health status")
        prometheus_lines.append(f"# TYPE app_health_status gauge")
        prometheus_lines.append(f'app_health_status{{component="cms"}} {health_status}')
        
        prometheus_output = "\n".join(prometheus_lines)
        return HttpResponse(prometheus_output, content_type='text/plain')
        
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return JsonResponse({
            'error': 'Failed to generate metrics',
            'detail': str(e),
        }, status=500)


@require_GET
@csrf_exempt
def metrics_json(request):
    """
    JSON metrics endpoint for detailed metrics.
    """
    from cms_project.monitoring_utils import get_comprehensive_metrics
    
    try:
        metrics_data = get_comprehensive_metrics()
        return JsonResponse(metrics_data, status=200)
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return JsonResponse({
            'error': 'Failed to get metrics',
            'detail': str(e),
        }, status=500)


@require_GET
@csrf_exempt
def status(request):
    """
    Application status endpoint with detailed information.
    """
    from cms_project.monitoring_utils import system_monitor, application_monitor
    
    try:
        system_health = system_monitor.check_system_health()
        app_metrics = application_monitor.get_application_metrics()
        perf_summary = application_monitor.get_performance_summary()
        
        status_data = {
            'timestamp': time.time(),
            'application': {
                'name': 'CMS Project',
                'version': '1.0.0',
                'environment': 'development' if settings.DEBUG else 'production',
                'debug': settings.DEBUG,
                'timezone': settings.TIME_ZONE,
            },
            'system': system_health,
            'performance': perf_summary,
            'requests': {
                'total': app_metrics.get('requests', {}).get('total', 0),
                'by_method': app_metrics.get('requests', {}).get('by_method', {}),
            },
            'database': {
                'engine': settings.DATABASES['default']['ENGINE'],
                'name': settings.DATABASES['default'].get('NAME', 'unknown'),
            },
            'cache': {
                'backend': settings.CACHES['default']['BACKEND'],
            },
        }
        
        return JsonResponse(status_data, status=200)
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return JsonResponse({
            'error': 'Failed to get status',
            'detail': str(e),
        }, status=500)


@require_GET
@csrf_exempt
def info(request):
    """
    Application information endpoint.
    """
    info_data = {
        'application': {
            'name': 'CMS Project',
            'description': 'Content Management System with Ticket Tracking',
            'version': '1.0.0',
        },
        'framework': {
            'django': '6.0.4',
            'python': '3.8+',
        },
        'environment': {
            'debug': settings.DEBUG,
            'timezone': settings.TIME_ZONE,
            'language_code': settings.LANGUAGE_CODE,
            'allowed_hosts': settings.ALLOWED_HOSTS,
        },
        'database': {
            'engine': settings.DATABASES['default']['ENGINE'],
            'name': settings.DATABASES['default'].get('NAME', 'unknown'),
            'host': settings.DATABASES['default'].get('HOST', 'localhost'),
        },
        'cache': {
            'backend': settings.CACHES['default']['BACKEND'],
        },
        'security': {
            'csrf_protected': True,
            'session_secure': settings.SESSION_COOKIE_SECURE,
            'https_redirect': settings.SECURE_SSL_REDIRECT,
        },
        'timestamp': time.time(),
    }
    
    return JsonResponse(info_data, status=200)