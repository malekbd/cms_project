"""
Database routers for primary/replica database configuration.
Enables read/write splitting for improved database performance.
"""

import random
from django.conf import settings


class PrimaryReplicaRouter:
    """
    A router to control all database operations on models in the
    application and perform read/write splitting.
    """
    
    def db_for_read(self, model, **hints):
        """
        Attempts to read from replica DB.
        """
        # Check if hints specify a database
        if 'instance' in hints:
            instance = hints['instance']
            if instance and instance._state.db:
                return instance._state.db
        
        # Use read replica if available and configured
        if hasattr(settings, 'DATABASES') and 'read_replica' in settings.DATABASES:
            # For certain models or queries, we might want to always use primary
            # For now, randomly choose between primary and replica for load balancing
            # In production, you might want more sophisticated logic
            if random.random() < 0.8:  # 80% chance to use replica
                return 'read_replica'
        
        return 'default'
    
    def db_for_write(self, model, **hints):
        """
        Writes always go to primary.
        """
        # Check if hints specify a database
        if 'instance' in hints:
            instance = hints['instance']
            if instance and instance._state.db:
                return instance._state.db
        
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both objects are in the same database.
        """
        db_set = {'default', 'read_replica'}
        
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return obj1._state.db == obj2._state.db
        
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure migrations only run on the primary database.
        """
        if db == 'read_replica':
            return False  # Never migrate read replicas
        return True  # Allow migrations on default database
    
    def allow_join(self, *args, **kwargs):
        """
        Allow joins between tables in the same database.
        """
        return True


class ModelSpecificRouter:
    """
    Route specific models to specific databases.
    """
    
    # Models that should always use the primary database
    PRIMARY_ONLY_MODELS = {
        'auth.User',
        'auth.Group',
        'auth.Permission',
        'sessions.Session',
        'admin.LogEntry',
    }
    
    # Models that can use read replicas
    REPLICA_ALLOWED_MODELS = {
        'tickets.Ticket',
        'tickets.Comment',
        'tickets.UserProfile',
    }
    
    def db_for_read(self, model, **hints):
        """
        Determine which database to use for read operations.
        """
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"
        
        # Always use primary for certain critical models
        if model_name in self.PRIMARY_ONLY_MODELS:
            return 'default'
        
        # Allow replicas for certain models
        if model_name in self.REPLICA_ALLOWED_MODELS:
            if hasattr(settings, 'DATABASES') and 'read_replica' in settings.DATABASES:
                return 'read_replica'
        
        return 'default'
    
    def db_for_write(self, model, **hints):
        """
        All writes go to primary.
        """
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a consistent database can be used.
        """
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only allow migrations on the primary database.
        """
        if db == 'read_replica':
            return False
        return True


# Default router
class DefaultRouter:
    """
    Default database router that uses primary for everything.
    Useful for development or when replicas are not configured.
    """
    
    def db_for_read(self, model, **hints):
        return 'default'
    
    def db_for_write(self, model, **hints):
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True


# Choose which router to use based on configuration
def get_database_router():
    """
    Get the appropriate database router based on configuration.
    """
    if hasattr(settings, 'DATABASES') and 'read_replica' in settings.DATABASES:
        if getattr(settings, 'USE_MODEL_SPECIFIC_ROUTING', False):
            return ModelSpecificRouter()
        return PrimaryReplicaRouter()
    return DefaultRouter()