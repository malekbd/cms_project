import logging
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404
from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """Middleware to handle errors gracefully and provide consistent error responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """Handle exceptions and log them appropriately."""
        
        # Log the exception with context
        logger.error(
            f"Exception occurred: {type(exception).__name__}: {str(exception)} "
            f"at {request.path} from {request.META.get('REMOTE_ADDR', 'unknown')}",
            exc_info=True,
            extra={
                'request_path': request.path,
                'request_method': request.method,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
            }
        )

        # Handle different types of exceptions
        if isinstance(exception, ValidationError):
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'error': 'Validation Error',
                    'message': str(exception),
                    'status': 400
                }, status=400)
            return None  # Let Django handle ValidationError normally

        elif isinstance(exception, DatabaseError):
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'error': 'Database Error',
                    'message': 'A database error occurred. Please try again later.',
                    'status': 500
                }, status=500)
            return None

        elif isinstance(exception, Http404):
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'error': 'Not Found',
                    'message': 'The requested resource was not found.',
                    'status': 404
                }, status=404)
            return None

        # Generic error handling
        if settings.DEBUG:
            return None  # Let Django show the debug page in development
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred. Please try again later.',
                'status': 500
            }, status=500)
        
        return None


class SecurityHeadersMiddleware:
    """Middleware to add security headers to responses including CSP."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Add CSP header if enabled
        if getattr(settings, 'CSP_ENABLED', False):
            csp_header = self._build_csp_header()
            response['Content-Security-Policy'] = csp_header
        
        # HSTS header for production
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Additional security headers
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        
        return response
    
    def _build_csp_header(self):
        """Build Content Security Policy header."""
        directives = []
        
        # Default source
        if hasattr(settings, 'CSP_DEFAULT_SRC'):
            directives.append(f"default-src {' '.join(settings.CSP_DEFAULT_SRC)}")
        
        # Script sources
        if hasattr(settings, 'CSP_SCRIPT_SRC'):
            directives.append(f"script-src {' '.join(settings.CSP_SCRIPT_SRC)}")
        
        # Style sources
        if hasattr(settings, 'CSP_STYLE_SRC'):
            directives.append(f"style-src {' '.join(settings.CSP_STYLE_SRC)}")
        
        # Image sources
        if hasattr(settings, 'CSP_IMG_SRC'):
            directives.append(f"img-src {' '.join(settings.CSP_IMG_SRC)}")
        
        # Font sources
        if hasattr(settings, 'CSP_FONT_SRC'):
            directives.append(f"font-src {' '.join(settings.CSP_FONT_SRC)}")
        
        # Connect sources
        if hasattr(settings, 'CSP_CONNECT_SRC'):
            directives.append(f"connect-src {' '.join(settings.CSP_CONNECT_SRC)}")
        
        # Frame sources
        if hasattr(settings, 'CSP_FRAME_SRC'):
            directives.append(f"frame-src {' '.join(settings.CSP_FRAME_SRC)}")
        else:
            directives.append("frame-src 'none'")
        
        # Object sources
        directives.append("object-src 'none'")
        
        # Base URI
        directives.append("base-uri 'self'")
        
        # Form action
        directives.append("form-action 'self'")
        
        # Frame ancestors
        directives.append("frame-ancestors 'none'")
        
        return '; '.join(directives)
