"""
Monitoring utilities for the CMS project.
Provides system monitoring, health checks, and metrics collection.
"""

import time
import psutil
import logging
import json
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.db import connections
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SystemMonitor:
    """
    Monitor system resources and performance.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics_history = []
        self.max_history_size = 1000
        
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive system metrics.
        
        Returns:
            Dictionary with system metrics
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent(interval=0.1)
            
            metrics = {
                'timestamp': time.time(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency_current': cpu_freq.current if cpu_freq else None,
                    'frequency_min': cpu_freq.min if cpu_freq else None,
                    'frequency_max': cpu_freq.max if cpu_freq else None,
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free,
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent,
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent,
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0,
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                },
                'process': {
                    'pid': process.pid,
                    'memory_rss': process_memory.rss,
                    'memory_vms': process_memory.vms,
                    'cpu_percent': process_cpu,
                    'threads': process.num_threads(),
                    'create_time': process.create_time(),
                },
                'uptime': time.time() - self.start_time,
            }
            
            # Store in history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {
                'timestamp': time.time(),
                'error': str(e),
            }
    
    def get_metrics_summary(self, window_minutes: int = 5) -> Dict[str, Any]:
        """
        Get summary of metrics over a time window.
        
        Args:
            window_minutes: Time window in minutes
            
        Returns:
            Summary statistics
        """
        window_seconds = window_minutes * 60
        cutoff = time.time() - window_seconds
        
        recent_metrics = [
            m for m in self.metrics_history 
            if m['timestamp'] > cutoff
        ]
        
        if not recent_metrics:
            return {'error': 'No metrics in specified window'}
        
        summary = {
            'window_minutes': window_minutes,
            'sample_count': len(recent_metrics),
            'cpu_avg': sum(m['cpu']['percent'] for m in recent_metrics) / len(recent_metrics),
            'memory_avg': sum(m['memory']['percent'] for m in recent_metrics) / len(recent_metrics),
            'disk_avg': sum(m['disk']['percent'] for m in recent_metrics) / len(recent_metrics),
            'timestamp': time.time(),
        }
        
        return summary
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Check system health and identify potential issues.
        
        Returns:
            Health check results with warnings
        """
        metrics = self.get_system_metrics()
        warnings = []
        
        # Check CPU usage
        if metrics['cpu']['percent'] > 80:
            warnings.append(f"High CPU usage: {metrics['cpu']['percent']}%")
        
        # Check memory usage
        if metrics['memory']['percent'] > 85:
            warnings.append(f"High memory usage: {metrics['memory']['percent']}%")
        
        # Check disk usage
        if metrics['disk']['percent'] > 90:
            warnings.append(f"High disk usage: {metrics['disk']['percent']}%")
        
        # Check swap usage
        if metrics['swap']['percent'] > 50:
            warnings.append(f"High swap usage: {metrics['swap']['percent']}%")
        
        health = {
            'timestamp': metrics['timestamp'],
            'status': 'healthy' if not warnings else 'warning',
            'warnings': warnings,
            'metrics': {
                'cpu_percent': metrics['cpu']['percent'],
                'memory_percent': metrics['memory']['percent'],
                'disk_percent': metrics['disk']['percent'],
            },
        }
        
        return health


class ApplicationMonitor:
    """
    Monitor application-specific metrics.
    """
    
    def __init__(self):
        self.request_counts = {
            'total': 0,
            'by_method': {},
            'by_status': {},
            'by_endpoint': {},
        }
        self.error_counts = {}
        self.start_time = time.time()
    
    def record_request(self, request, response):
        """
        Record request metrics.
        """
        self.request_counts['total'] += 1
        
        method = request.method
        self.request_counts['by_method'][method] = self.request_counts['by_method'].get(method, 0) + 1
        
        status = response.status_code
        status_group = f"{status // 100}xx"
        self.request_counts['by_status'][status_group] = self.request_counts['by_status'].get(status_group, 0) + 1
        
        endpoint = request.path
        self.request_counts['by_endpoint'][endpoint] = self.request_counts['by_endpoint'].get(endpoint, 0) + 1
    
    def record_error(self, error_type: str):
        """
        Record error metrics.
        """
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_application_metrics(self) -> Dict[str, Any]:
        """
        Get application performance metrics.
        
        Returns:
            Application metrics
        """
        # Get cache stats if available
        cache_stats = {}
        try:
            from cms_project.cache_utils import get_cache_stats
            cache_stats = get_cache_stats()
        except ImportError:
            pass
        
        # Get database metrics if available
        db_metrics = {}
        try:
            from cms_project.db_monitoring import get_database_metrics
            db_metrics = get_database_metrics()
        except ImportError:
            pass
        
        uptime = time.time() - self.start_time
        
        metrics = {
            'timestamp': time.time(),
            'uptime_seconds': uptime,
            'requests': self.request_counts,
            'errors': self.error_counts,
            'cache': cache_stats,
            'database': db_metrics,
            'django_settings': {
                'debug': settings.DEBUG,
                'allowed_hosts': len(settings.ALLOWED_HOSTS),
                'installed_apps': len(settings.INSTALLED_APPS),
                'middleware': len(settings.MIDDLEWARE),
            },
        }
        
        return metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.
        
        Returns:
            Performance summary
        """
        metrics = self.get_application_metrics()
        
        summary = {
            'timestamp': metrics['timestamp'],
            'uptime_hours': metrics['uptime_seconds'] / 3600,
            'total_requests': metrics['requests']['total'],
            'requests_per_hour': metrics['requests']['total'] / (metrics['uptime_seconds'] / 3600) if metrics['uptime_seconds'] > 0 else 0,
            'error_count': sum(metrics['errors'].values()),
            'cache_status': metrics['cache'].get('connection', False) if metrics.get('cache') else False,
            'database_status': metrics['database'].get('overall_status', 'unknown') if metrics.get('database') else 'unknown',
        }
        
        return summary


class HealthCheck:
    """
    Comprehensive health check for the application.
    """
    
    @staticmethod
    def perform_health_check() -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Health check results
        """
        checks = {}
        
        # Database health check
        checks['database'] = HealthCheck._check_database()
        
        # Cache health check
        checks['cache'] = HealthCheck._check_cache()
        
        # Storage health check
        checks['storage'] = HealthCheck._check_storage()
        
        # Application health check
        checks['application'] = HealthCheck._check_application()
        
        # Determine overall status
        all_healthy = all(check['status'] == 'healthy' for check in checks.values())
        overall_status = 'healthy' if all_healthy else 'unhealthy'
        
        return {
            'timestamp': time.time(),
            'status': overall_status,
            'checks': checks,
        }
    
    @staticmethod
    def _check_database() -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test connection
            conn = connections['default']
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            latency = time.time() - start_time
            
            return {
                'status': 'healthy' if result and result[0] == 1 else 'unhealthy',
                'latency_ms': round(latency * 1000, 2),
                'engine': conn.settings_dict['ENGINE'],
                'database': conn.settings_dict.get('NAME', 'unknown'),
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': None,
            }
    
    @staticmethod
    def _check_cache() -> Dict[str, Any]:
        """Check cache connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test cache
            test_key = 'health_check'
            test_value = 'ok'
            
            cache.set(test_key, test_value, 10)
            retrieved = cache.get(test_key)
            
            latency = time.time() - start_time
            
            return {
                'status': 'healthy' if retrieved == test_value else 'unhealthy',
                'latency_ms': round(latency * 1000, 2),
                'backend': settings.CACHES['default']['BACKEND'],
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': None,
            }
    
    @staticmethod
    def _check_storage() -> Dict[str, Any]:
        """Check storage availability."""
        try:
            # Check media directory
            media_root = settings.MEDIA_ROOT
            media_writable = media_root.exists() and os.access(media_root, os.W_OK)
            
            # Check static directory
            static_root = settings.STATIC_ROOT
            static_writable = static_root.exists() and os.access(static_root, os.W_OK)
            
            # Check logs directory
            logs_dir = settings.BASE_DIR / 'logs'
            logs_writable = logs_dir.exists() and os.access(logs_dir, os.W_OK)
            
            return {
                'status': 'healthy' if all([media_writable, static_writable, logs_writable]) else 'warning',
                'media_writable': media_writable,
                'static_writable': static_writable,
                'logs_writable': logs_writable,
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }
    
    @staticmethod
    def _check_application() -> Dict[str, Any]:
        """Check application health."""
        try:
            # Check if settings are loaded
            settings_loaded = hasattr(settings, 'DEBUG') and hasattr(settings, 'SECRET_KEY')
            
            # Check if middleware is configured
            middleware_configured = len(settings.MIDDLEWARE) > 0
            
            # Check if apps are installed
            apps_installed = len(settings.INSTALLED_APPS) > 0
            
            return {
                'status': 'healthy' if all([settings_loaded, middleware_configured, apps_installed]) else 'warning',
                'settings_loaded': settings_loaded,
                'middleware_configured': middleware_configured,
                'apps_installed': apps_installed,
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


# Global monitor instances
system_monitor = SystemMonitor()
application_monitor = ApplicationMonitor()
health_check = HealthCheck()


def get_comprehensive_metrics() -> Dict[str, Any]:
    """
    Get all metrics in a single call.
    
    Returns:
        Comprehensive metrics dictionary
    """
    return {
        'timestamp': time.time(),
        'system': system_monitor.get_system_metrics(),
        'application': application_monitor.get_application_metrics(),
        'health': health_check.perform_health_check(),
        'performance_summary': application_monitor.get_performance_summary(),
        'system_health': system_monitor.check_system_health(),
    }


# Import os for storage check
import os