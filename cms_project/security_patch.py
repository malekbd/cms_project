"""
Monkey patch to fix missing on_delete in django-security ForeignKey.
This must be imported before any app loading.
"""
import django.db.models.fields.related
from django.db.models import CASCADE

original_init = django.db.models.fields.related.ForeignKey.__init__

def patched_init(self, *args, **kwargs):
    # Determine if on_delete is provided
    # Signature: ForeignKey(to, on_delete, **kwargs)
    # If args length >= 2, second arg is on_delete
    # If args length == 1, on_delete is missing (must be added)
    # If on_delete in kwargs, it's already provided
    if 'on_delete' in kwargs:
        # Already provided as keyword
        pass
    elif len(args) >= 2:
        # on_delete is second positional argument
        pass
    else:
        # on_delete missing, add as keyword
        kwargs['on_delete'] = CASCADE
    # Call original __init__
    return original_init(self, *args, **kwargs)

# Apply patch
django.db.models.fields.related.ForeignKey.__init__ = patched_init

# Also patch django.db.models.ForeignKey (which is an alias)
import django.db.models
django.db.models.ForeignKey = django.db.models.fields.related.ForeignKey