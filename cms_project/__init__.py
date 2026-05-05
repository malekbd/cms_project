# Apply security patch for missing on_delete in django-security
try:
    from .security_patch import *
except ImportError:
    pass