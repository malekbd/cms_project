from pathlib import Path
import os
import sys
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Enhanced Security Headers
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=DEBUG is False, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000 if DEBUG is False else 0, cast=int)  # 1 year in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=DEBUG is False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=DEBUG is False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=DEBUG is False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=DEBUG is False, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'  # 'Lax' for better UX while maintaining security
CSRF_COOKIE_HTTPONLY = False  # Must be False for JavaScript to access CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = config('SESSION_EXPIRE_AT_BROWSER_CLOSE', default=False, cast=bool)
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1209600, cast=int)  # 2 weeks default

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Password hashers (use bcrypt for stronger password hashing)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
]

# Security Configuration
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)
LOGIN_TIMEOUT_MINUTES = config('LOGIN_TIMEOUT_MINUTES', default=30, cast=int)

# Content Security Policy (CSP) - Comprehensive configuration
CSP_ENABLED = config('CSP_ENABLED', default=DEBUG is False, cast=bool)
if CSP_ENABLED:
    CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "'nonce'", "'unsafe-inline'")  # Allow nonce-based inline scripts, keep unsafe-inline for legacy event handlers
    CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com", "'nonce'", "'unsafe-inline'")
    CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")
    CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "data:")
    CSP_CONNECT_SRC = ("'self'",)
    CSP_FRAME_SRC = ("'self'",)
    CSP_MEDIA_SRC = ("'self'",)
    CSP_MANIFEST_SRC = ("'self'",)
    CSP_WORKER_SRC = ("'self'", "blob:")
    CSP_CHILD_SRC = ("'self'",)

# Django Axes configuration (brute force protection)
AXES_FAILURE_LIMIT = 5  # 5 failed login attempts
AXES_COOLOFF_TIME = 1  # 1 hour lockout
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'panel/login.html'
AXES_META_PRECEDENCE_ORDER = [
    'HTTP_X_FORWARDED_FOR',
    'REMOTE_ADDR',
]

if 'test' in sys.argv:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, 'testserver']
    # Use faster password hasher for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Security apps
    'axes',  # Login security and brute force protection
    'csp',  # Content Security Policy
    'security',  # Additional security features
    
    # API & Documentation
    'rest_framework',
    'drf_spectacular',
    
    # Project apps
    'tickets',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',  # Add response compression
    'cms_project.metrics_exporter.MetricsMiddleware',  # Metrics collection for monitoring
    'cms_project.security_hardening.EnhancedSecurityMiddleware',  # Enhanced security headers and protections
    'cms_project.security_utils.XSSProtectionMiddleware',  # XSS protection and input sanitization
    'cms_project.rate_limiting.RateLimitMiddleware',  # Rate limiting for API abuse protection
    'cms_project.rate_limiting.BruteForceProtectionMiddleware',  # Brute force attack protection
    'cms_project.auth_middleware.AuthenticationSecurityMiddleware',  # Enhanced authentication security
    'cms_project.auth_middleware.AuthorizationMiddleware',  # Authorization enforcement
    'cms_project.middleware.SecurityHeadersMiddleware',
    'cms_project.performance_middleware.PerformanceMiddleware',  # Performance monitoring
    'cms_project.performance_middleware.QueryOptimizationMiddleware',  # Query optimization
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'cms_project.middleware.ErrorHandlingMiddleware',
]

ROOT_URLCONF = 'cms_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tickets.context_processors.panel_branding',
            ],
        },
    },
]

WSGI_APPLICATION = 'cms_project.wsgi.application'

# Use SQLite for tests to avoid PostgreSQL dependency
if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
else:
    # Enhanced PostgreSQL configuration with connection pooling and read replicas
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': config('CONN_MAX_AGE', default=600, cast=int),  # Increased to 10 minutes
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 5,  # Reduced from 10 to 5 seconds
                'keepalives': 1,
                'keepalives_idle': 60,  # Increased from 30 to 60 seconds
                'keepalives_interval': 10,  # Increased from 5 to 10 seconds
                'keepalives_count': 5,
                'sslmode': config('DB_SSL_MODE', default='prefer'),  # SSL support
                'application_name': 'cms_project',
                # Connection pool settings (when using external pooling like PgBouncer)
                'pool_size': config('DB_POOL_SIZE', default=20, cast=int),
                'max_overflow': config('DB_MAX_OVERFLOW', default=10, cast=int),
                'pool_timeout': config('DB_POOL_TIMEOUT', default=30, cast=int),
                'pool_recycle': config('DB_POOL_RECYCLE', default=3600, cast=int),  # Recycle connections every hour
                # Performance optimizations
                'statement_timeout': config('DB_STATEMENT_TIMEOUT', default=30000, cast=int),  # 30 seconds
                'idle_in_transaction_session_timeout': config('DB_IDLE_TIMEOUT', default=10000, cast=int),  # 10 seconds
            },
            'TEST': {
                'NAME': config('TEST_DB_NAME', default='test_cms_project'),
                'SERIALIZE': False,  # Faster tests
            },
            # Connection monitoring
            'ATOMIC_REQUESTS': False,  # Keep False for performance
            'AUTOCOMMIT': True,
        }
    }
    
    # Add read replica configuration if enabled
    if config('DB_READ_REPLICA_ENABLED', default=False, cast=bool):
        DATABASES['read_replica'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_READ_NAME', default=config('DB_NAME')),
            'USER': config('DB_READ_USER', default=config('DB_USER')),
            'PASSWORD': config('DB_READ_PASSWORD', default=config('DB_PASSWORD')),
            'HOST': config('DB_READ_HOST', default=config('DB_HOST', default='localhost')),
            'PORT': config('DB_READ_PORT', default=config('DB_PORT', default='5432')),
            'CONN_MAX_AGE': config('DB_READ_CONN_MAX_AGE', default=300, cast=int),  # 5 minutes for read replicas
            'OPTIONS': {
                'connect_timeout': 5,
                'keepalives': 1,
                'keepalives_idle': 60,
                'sslmode': config('DB_SSL_MODE', default='prefer'),
                'application_name': 'cms_project_read',
            },
        }
        
        # Django REST Framework configuration
        REST_FRAMEWORK = {
            'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
                'rest_framework.authentication.BasicAuthentication',
            ],
            'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
            'PAGE_SIZE': 50,
        }
        
        # drf-spectacular configuration for OpenAPI 3.0
        SPECTACULAR_SETTINGS = {
            'TITLE': 'CMS Ticket Management API',
            'DESCRIPTION': 'API for managing customer support tickets',
            'VERSION': '1.0.0',
            'SERVE_INCLUDE_SCHEMA': False,
            'SWAGGER_UI_SETTINGS': {
                'deepLinking': True,
                'persistAuthorization': True,
            },
        }
        
        # Configure database router for read/write splitting
        DATABASE_ROUTERS = ['cms_project.db_routers.PrimaryReplicaRouter']
    
# Database connection pooling via psycopg2-pool is not enabled by default.
# Removed non-standard Django OPTIONS in favor of stable, well-supported configuration.
    
    # Database performance settings
    DATABASES['default']['OPTIONS']['options'] = f"-c statement_timeout={config('DB_STATEMENT_TIMEOUT', default=30000, cast=int)}"
    
    # Configure connection health checks
    if config('DB_CONNECTION_HEALTH_CHECKS', default=True, cast=bool):
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True  # Better for connection pooling

# Cache configuration - Enhanced Redis setup with multiple cache backends
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
REDIS_PASSWORD = config('REDIS_PASSWORD', default='')
REDIS_DB_CACHE = config('REDIS_DB_CACHE', default=0, cast=int)
REDIS_DB_SESSION = config('REDIS_DB_SESSION', default=1, cast=int)
REDIS_DB_CELERY = config('REDIS_DB_CELERY', default=2, cast=int)

# Build Redis URL with password if provided
if REDIS_PASSWORD:
    REDIS_CACHE_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_URL.split('://')[1].split('@')[-1]}/{REDIS_DB_CACHE}"
else:
    REDIS_CACHE_URL = f"{REDIS_URL}/{REDIS_DB_CACHE}"

try:
    # Try to use Redis if available
    import redis
    import django_redis
    
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_CACHE_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 200,
                    'retry_on_timeout': True,
                    'socket_keepalive': True,
                },
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 10,
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                'COMPRESSOR_LEVEL': 5,  # Balanced compression level
                'IGNORE_EXCEPTIONS': True,  # Prevent cache failures from breaking the app
                'PARSER_CLASS': 'redis.connection.HiredisParser' if config('USE_HIREDIS', default=False, cast=bool) else 'redis.connection.PythonParser',
            },
            'KEY_PREFIX': 'cms_cache',
            'TIMEOUT': 600,  # 10 minutes default cache timeout
            'KEY_FUNCTION': 'cms_project.cache_utils.make_cache_key',
        },
        'session': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f"{REDIS_URL}/{REDIS_DB_SESSION}" if not REDIS_PASSWORD else f"redis://:{REDIS_PASSWORD}@{REDIS_URL.split('://')[1].split('@')[-1]}/{REDIS_DB_SESSION}",
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {'max_connections': 50},
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'KEY_PREFIX': 'cms_session',
            'TIMEOUT': 1209600,  # 2 weeks for sessions
        },
        'rate_limit': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f"{REDIS_URL}/3" if not REDIS_PASSWORD else f"redis://:{REDIS_PASSWORD}@{REDIS_URL.split('://')[1].split('@')[-1]}/3",
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {'max_connections': 30},
                'SOCKET_CONNECT_TIMEOUT': 2,
                'SOCKET_TIMEOUT': 2,
            },
            'KEY_PREFIX': 'cms_rate',
            'TIMEOUT': 3600,  # 1 hour for rate limiting
        }
    }
    
    # Use Redis for session storage in production
    if not DEBUG:
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        SESSION_CACHE_ALIAS = 'session'
    
    # Configure Redis as message broker for Celery (optional)
    CELERY_BROKER_URL = f"{REDIS_URL}/{REDIS_DB_CELERY}" if not REDIS_PASSWORD else f"redis://:{REDIS_PASSWORD}@{REDIS_URL.split('://')[1].split('@')[-1]}/{REDIS_DB_CELERY}"
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
    
except ImportError:
    # Fallback to local memory cache with improved configuration
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'default-cache',
            'TIMEOUT': 300,
            'OPTIONS': {
                'MAX_ENTRIES': 5000,
                'CULL_FREQUENCY': 3,  # Remove 1/3 of entries when max reached
            }
        },
        'session': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'session-cache',
            'TIMEOUT': 1209600,
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            }
        },
        'rate_limit': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'rate-limit-cache',
            'TIMEOUT': 3600,
            'OPTIONS': {
                'MAX_ENTRIES': 2000,
            }
        }
    }
    
    # Log warning about Redis not being available
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Redis not available, using local memory cache. Performance may be degraded.")

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Static files optimization
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Browser caching for static files (1 year)
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Add cache control headers for static files in production
if not DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Authentication
LOGIN_URL = '/panel/login/'
LOGIN_REDIRECT_URL = '/panel/'
LOGOUT_REDIRECT_URL = '/panel/login/'

# Enhanced Logging Configuration with Monitoring
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'security': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message} - IP: {ip} User: {user} Action: {action}',
            'style': '{',
        },
        # Removed json-based structured formatter; using verbose/simple instead
        'performance': {
            'format': '{levelname} {asctime} {module} {duration:.3f}s {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'production_console': {
            'level': 'INFO',
            'filters': ['require_debug_false'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': config('LOG_LEVEL', default='INFO'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'security',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
        'performance_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'performance.log',
            'formatter': 'performance',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'database_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'database.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': False,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'production_console', 'file', 'error_file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'production_console', 'error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['database_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'production_console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'tickets': {
            'handlers': ['console', 'production_console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        },
        'security': {
            'handlers': ['security_file', 'production_console', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'cms_project': {
            'handlers': ['console', 'production_console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'cms_project.auth_middleware': {
            'handlers': ['security_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms_project.rate_limiting': {
            'handlers': ['security_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms_project.security_utils': {
            'handlers': ['security_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms_project.performance_middleware': {
            'handlers': ['performance_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms_project.db_monitoring': {
            'handlers': ['database_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms_project.cache_utils': {
            'handlers': ['performance_file', 'production_console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
