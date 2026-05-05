"""
Metrics exporter for the CMS project.
Exposes application metrics in Prometheus format and provides health endpoints.
"""

import time
import psutil
import logging
from typing import Dict, Any, List
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views import View
import threading
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and exports application metrics.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.max_metrics_history = 1000
        self.metrics_lock = threading.Lock()
        
        # Initialize metrics storage
        self.metrics = defaultdict(list)
        
    def record_request(self, path: str, method: str, status_code: int, duration: float):
        """
        Record a request for metrics.
        """
        with self.metrics_lock:
            self.request_count += 1
            
            if status_code >= 400:
                self.error_count += 1
            
            # Store response time
            self.response_times.append(duration)
            if len(self.response_times) > self.max_metrics_history:
                self.response_times.pop(0)
            
            # Store per-endpoint metrics
            endpoint_key = f"{method}:{path}"
            self.metrics[endpoint_key].append({
                'timestamp': time.time(),
                'duration': duration,
                'status': status_code
            })
            
            # Trim old metrics
            if len(self.metrics[endpoint_key]) > 100:
                self.metrics[endpoint_key] = self.metrics[endpoint_key][-100:]
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-level metrics.
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'percent': swap.percent,
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent,
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                },
                'process': {
                    'pid': process.pid,
                    'memory_percent': process.memory_percent(),
                    'cpu_percent': process.cpu_percent(interval=0.1),
                    'threads': process.num_threads(),
                },
            }
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {'error': str(e)}
    
    def get_application_metrics(self) -> Dict[str, Any]:
        """
        Get application-level metrics.
        """
        with self.metrics_lock:
            # Calculate response time statistics
            if self.response_times:
                avg_response = sum(self.response_times) / len(self.response_times)
                max_response = max(self.response_times)
                min_response = min(self.response_times)
            else:
                avg_response = max_response = min_response = 0
            
            # Calculate error rate
            error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
            
            # Get database metrics
            db_metrics = {}
            try:
                for alias, conn in connections.items():
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT 1")
                            db_metrics[alias] = {
                                'connected': True,
                                'vendor': conn.vendor,
                            }
                    except Exception as e:
                        db_metrics[alias] = {
                            'connected': False,
                            'error': str(e),
                        }
            except Exception as e:
                db_metrics = {'error': str(e)}
            
            # Get cache metrics
            cache_metrics = {}
            try:
                # Test cache connection
                test_key = 'metrics_test'
                cache.set(test_key, 'test', 10)
                cached = cache.get(test_key)
                cache_metrics['connected'] = cached == 'test'
                cache_metrics['backend'] = settings.CACHES['default']['BACKEND']
            except Exception as e:
                cache_metrics['connected'] = False
                cache_metrics['error'] = str(e)
            
            return {
                'requests': {
                    'total': self.request_count,
                    'errors': self.error_count,
                    'error_rate': round(error_rate, 2),
                },
                'response_times': {
                    'avg_ms': round(avg_response * 1000, 2),
                    'max_ms': round(max_response * 1000, 2),
                    'min_ms': round(min_response * 1000, 2),
                    'p95_ms': self._calculate_percentile(95) if self.response_times else 0,
                    'p99_ms': self._calculate_percentile(99) if self.response_times else 0,
                },
                'uptime': {
                    'seconds': time.time() - self.start_time,
                    'hours': (time.time() - self.start_time) / 3600,
                },
                'database': db_metrics,
                'cache': cache_metrics,
                'endpoints': {
                    'count': len(self.metrics),
                    'top_endpoints': self._get_top_endpoints(5),
                },
            }
    
    def _calculate_percentile(self, percentile: float) -> float:
        """
        Calculate percentile of response times.
        """
        if not self.response_times:
            return 0
        
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * percentile / 100)
        return round(sorted_times[index] * 1000, 2)
    
    def _get_top_endpoints(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top endpoints by request count.
        """
        endpoints = []
        for endpoint, metrics in self.metrics.items():
            avg_duration = sum(m['duration'] for m in metrics) / len(metrics) if metrics else 0
            error_count = sum(1 for m in metrics if m['status'] >= 400)
            
            endpoints.append({
                'endpoint': endpoint,
                'request_count': len(metrics),
                'avg_duration_ms': round(avg_duration * 1000, 2),
                'error_count': error_count,
            })
        
        # Sort by request count descending
        endpoints.sort(key=lambda x: x['request_count'], reverse=True)
        return endpoints[:limit]
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.
        """
        metrics = []
        
        # Application metrics
        app_metrics = self.get_application_metrics()
        
        metrics.append(f'# HELP cms_request_total Total number of requests')
        metrics.append(f'# TYPE cms_request_total counter')
        metrics.append(f'cms_request_total {app_metrics["requests"]["total"]}')
        
        metrics.append(f'# HELP cms_request_errors_total Total number of error responses')
        metrics.append(f'# TYPE cms_request_errors_total counter')
        metrics.append(f'cms_request_errors_total {app_metrics["requests"]["errors"]}')
        
        metrics.append(f'# HELP cms_response_time_avg_ms Average response time in milliseconds')
        metrics.append(f'# TYPE cms_response_time_avg_ms gauge')
        metrics.append(f'cms_response_time_avg_ms {app_metrics["response_times"]["avg_ms"]}')
        
        metrics.append(f'# HELP cms_response_time_max_ms Maximum response time in milliseconds')
        metrics.append(f'# TYPE cms_response_time_max_ms gauge')
        metrics.append(f'cms_response_time_max_ms {app_metrics["response_times"]["max_ms"]}')
        
        metrics.append(f'# HELP cms_uptime_seconds Application uptime in seconds')
        metrics.append(f'# TYPE cms_uptime_seconds gauge')
        metrics.append(f'cms_uptime_seconds {app_metrics["uptime"]["seconds"]}')
        
        # System metrics
        sys_metrics = self.get_system_metrics()
        if 'cpu' in sys_metrics:
            metrics.append(f'# HELP cms_cpu_percent CPU usage percentage')
            metrics.append(f'# TYPE cms_cpu_percent gauge')
            metrics.append(f'cms_cpu_percent {sys_metrics["cpu"]["percent"]}')
            
            metrics.append(f'# HELP cms_memory_percent Memory usage percentage')
            metrics.append(f'# TYPE cms_memory_percent gauge')
            metrics.append(f'cms_memory_percent {sys_metrics["memory"]["percent"]}')
            
            metrics.append(f'# HELP cms_disk_percent Disk usage percentage')
            metrics.append(f'# TYPE cms_disk_percent gauge')
            metrics.append(f'cms_disk_percent {sys_metrics["disk"]["percent"]}')
        
        return '\n'.join(metrics)


# Global metrics collector instance
metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """
    Middleware to collect request metrics.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Start timing
        start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics (exclude metrics endpoints themselves)
        if not request.path.startswith('/metrics') and not request.path.startswith('/health'):
            metrics_collector.record_request(
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                duration=duration
            )
        
        # Add performance header
        response['X-Response-Time'] = f'{duration:.3f}s'
        
        return response


@require_GET
def metrics_prometheus(request):
    """
    Export metrics in Prometheus format.
    """
    content = metrics_collector.export_prometheus()
    return HttpResponse(content, content_type='text/plain')


@require_GET
def metrics_json(request):
    """
    Export metrics in JSON format.
    """
    data = {
        'system': metrics_collector.get_system_metrics(),
        'application': metrics_collector.get_application_metrics(),
        'timestamp': time.time(),
    }
    return JsonResponse(data)


 
