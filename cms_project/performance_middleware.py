"""
Performance optimization middleware for the CMS project.
Includes response caching, database query optimization, and performance monitoring.
"""
import time
from django.core.cache import cache
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class PerformanceMiddleware:
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

        # --- Pre-view: track query baseline ---
        request._query_count_start = len(connection.queries)
        request._query_time_start = sum(
            float(q.get('time', 0)) for q in connection.queries
        )

        # --- Pre-view: set optimization hints ---
        if request.path in ('/panel/', '/panel/dashboard/'):
            request._optimize_for_dashboard = True

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
            if request.method == 'GET' and not request.path.startswith('/admin/'):
                response['Cache-Control'] = 'public, max-age=60'

        # --- Post-view: log query performance ---
        self._log_query_performance(request, response)

        return response

    def _log_query_performance(self, request, response):
        """Log database query performance after view execution."""
        if not hasattr(request, '_query_count_start'):
            return

        query_count = len(connection.queries) - request._query_count_start
        query_time = sum(
            float(q.get('time', 0))
            for q in connection.queries[request._query_count_start:]
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


class QueryOptimizationMiddleware:
    """
    Middleware to optimize database queries by:
    1. Ensuring proper connection management
    2. Adding query hints for common patterns
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Pre-view: add query optimization hints
        if request.path in ('/panel/', '/panel/dashboard/'):
            request._optimize_for_dashboard = True

        response = self.get_response(request)
        return response