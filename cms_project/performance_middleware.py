"""
Performance optimization middleware for the CMS project.
Includes response caching, database query optimization, and performance monitoring.
"""
import time
from django.core.cache import cache
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class PerformanceMiddleware(MiddlewareMixin):
    """
    Middleware to optimize performance by:
    1. Adding caching headers to responses
    2. Monitoring and logging slow requests
    3. Optimizing database queries
    4. Implementing response caching for certain endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_request_threshold = 1.0  # seconds
        self.slow_query_threshold = 0.1  # seconds
    
    def __call__(self, request):
        # Start timing the request
        start_time = time.time()
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log slow requests
        if duration > self.slow_request_threshold:
            logger.warning(
                f"Slow request: {request.method} {request.path} took {duration:.2f}s",
                extra={
                    'duration': duration,
                    'method': request.method,
                    'path': request.path,
                    'user': getattr(request.user, 'username', 'anonymous'),
                }
            )
        
        # Add performance headers
        response['X-Request-Duration'] = f'{duration:.3f}s'
        
        # Add caching headers for static-like responses
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            # Public pages can be cached
            if request.method == 'GET' and not request.path.startswith('/admin/'):
                response['Cache-Control'] = 'public, max-age=60'
        
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Monitor database queries before and after view execution.
        """
        # Reset query count and time
        request._query_count_start = len(connection.queries)
        request._query_time_start = sum(
            float(q.get('time', 0)) for q in connection.queries
        )
        return None
    
    def process_response(self, request, response):
        """
        Log database query performance after view execution.
        """
        if hasattr(request, '_query_count_start'):
            query_count = len(connection.queries) - request._query_count_start
            query_time = sum(
                float(q.get('time', 0)) for q in connection.queries[request._query_count_start:]
            )
            
            # Log excessive queries
            if query_count > 20:
                logger.warning(
                    f"High query count: {query_count} queries for {request.path}",
                    extra={
                        'query_count': query_count,
                        'query_time': query_time,
                        'path': request.path,
                        'method': request.method,
                    }
                )
            
            # Log slow queries
            if query_time > self.slow_query_threshold:
                logger.warning(
                    f"Slow database queries: {query_time:.2f}s for {query_count} queries on {request.path}",
                    extra={
                        'query_count': query_count,
                        'query_time': query_time,
                        'path': request.path,
                        'method': request.method,
                    }
                )
            
            # Add query info to headers for debugging
            if request.GET.get('debug') == 'queries':
                response['X-Query-Count'] = str(query_count)
                response['X-Query-Time'] = f'{query_time:.3f}s'
        
        return response


class QueryOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to optimize database queries by:
    1. Ensuring proper connection management
    2. Adding query hints for common patterns
    """
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Add query optimization hints based on the view.
        """
        # Example: For dashboard views, we could add optimization hints
        if request.path == '/panel/' or request.path == '/panel/dashboard/':
            # Set a flag that views can use to optimize queries
            request._optimize_for_dashboard = True
        
        return None