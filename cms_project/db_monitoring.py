"""
Database monitoring and connection pooling utilities for the CMS project.
Provides monitoring, health checks, and optimization for database connections.
"""

import time
import logging
from django.db import connection, connections
from django.db.utils import OperationalError, DatabaseError
from django.conf import settings
import threading
from collections import defaultdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """
    Monitor database connections and performance.
    """
    
    def __init__(self):
        self.connection_stats = defaultdict(lambda: {
            'queries': 0,
            'query_time': 0.0,
            'connections': 0,
            'errors': 0,
            'last_check': None,
        })
        self.monitoring_enabled = True
        self.slow_query_threshold = 1.0  # seconds
        self.max_connections_warning = 50
        
    def get_connection_info(self, alias: str = 'default') -> Dict[str, Any]:
        """
        Get information about a database connection.
        
        Args:
            alias: Database connection alias
            
        Returns:
            Dictionary with connection information
        """
        try:
            conn = connections[alias]
            info = {
                'alias': alias,
                'engine': conn.settings_dict['ENGINE'],
                'name': conn.settings_dict.get('NAME', 'N/A'),
                'host': conn.settings_dict.get('HOST', 'localhost'),
                'port': conn.settings_dict.get('PORT', 'default'),
                'user': conn.settings_dict.get('USER', 'N/A'),
                'conn_max_age': conn.settings_dict.get('CONN_MAX_AGE', 0),
                'in_transaction': conn.in_atomic_block,
                'is_usable': conn.is_usable(),
                'vendor': conn.vendor,
            }
            
            # Try to get PostgreSQL-specific info
            if conn.vendor == 'postgresql':
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT version(), current_database(), current_user, inet_server_addr()")
                        row = cursor.fetchone()
                        if row:
                            info.update({
                                'postgres_version': row[0],
                                'current_database': row[1],
                                'current_user': row[2],
                                'server_address': row[3],
                            })
                        
                        # Get connection count
                        cursor.execute("""
                            SELECT count(*) FROM pg_stat_activity 
                            WHERE datname = %s AND state = 'active'
                        """, [conn.settings_dict['NAME']])
                        info['active_connections'] = cursor.fetchone()[0]
                        
                        # Get database size
                        cursor.execute("""
                            SELECT pg_size_pretty(pg_database_size(%s))
                        """, [conn.settings_dict['NAME']])
                        info['database_size'] = cursor.fetchone()[0]
                except Exception as e:
                    info['postgres_error'] = str(e)
            
            return info
            
        except (OperationalError, DatabaseError, KeyError) as e:
            logger.error(f"Failed to get connection info for {alias}: {e}")
            return {
                'alias': alias,
                'error': str(e),
                'is_usable': False,
            }
    
    def check_connection_health(self, alias: str = 'default') -> Dict[str, Any]:
        """
        Check the health of a database connection.
        
        Args:
            alias: Database connection alias
            
        Returns:
            Health check results
        """
        start_time = time.time()
        health = {
            'alias': alias,
            'timestamp': start_time,
            'latency': None,
            'status': 'unknown',
            'error': None,
        }
        
        try:
            # Test connection with a simple query
            conn = connections[alias]
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
            latency = time.time() - start_time
            health.update({
                'latency': round(latency * 1000, 2),  # Convert to ms
                'status': 'healthy' if result and result[0] == 1 else 'unhealthy',
                'query_result': result[0] if result else None,
            })
            
            # Log slow connections
            if latency > 0.5:  # 500ms threshold
                logger.warning(f"Slow database connection for {alias}: {latency:.3f}s")
                
        except (OperationalError, DatabaseError) as e:
            health.update({
                'status': 'unhealthy',
                'error': str(e),
            })
            logger.error(f"Database connection health check failed for {alias}: {e}")
            
        return health
    
    def get_query_stats(self, alias: str = 'default') -> Dict[str, Any]:
        """
        Get query statistics for a connection.
        
        Args:
            alias: Database connection alias
            
        Returns:
            Query statistics
        """
        try:
            conn = connections[alias]
            queries = conn.queries if hasattr(conn, 'queries') else []
            
            stats = {
                'total_queries': len(queries),
                'slow_queries': 0,
                'total_query_time': 0.0,
                'queries_by_type': defaultdict(int),
            }
            
            for query in queries:
                query_time = float(query.get('time', 0))
                stats['total_query_time'] += query_time
                
                if query_time > self.slow_query_threshold:
                    stats['slow_queries'] += 1
                
                # Categorize query by type
                sql = query.get('sql', '').upper()
                if 'SELECT' in sql:
                    stats['queries_by_type']['SELECT'] += 1
                elif 'INSERT' in sql:
                    stats['queries_by_type']['INSERT'] += 1
                elif 'UPDATE' in sql:
                    stats['queries_by_type']['UPDATE'] += 1
                elif 'DELETE' in sql:
                    stats['queries_by_type']['DELETE'] += 1
                else:
                    stats['queries_by_type']['OTHER'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get query stats for {alias}: {e}")
            return {
                'error': str(e),
                'total_queries': 0,
            }
    
    def optimize_connections(self, alias: str = 'default') -> Dict[str, Any]:
        """
        Optimize database connections by closing idle connections.
        
        Args:
            alias: Database connection alias
            
        Returns:
            Optimization results
        """
        results = {
            'alias': alias,
            'connections_closed': 0,
            'connections_reopened': 0,
            'errors': [],
        }
        
        try:
            conn = connections[alias]
            
            # Close connection if it's old (based on CONN_MAX_AGE)
            conn_max_age = conn.settings_dict.get('CONN_MAX_AGE', 0)
            if conn_max_age > 0 and hasattr(conn, 'connection'):
                # Check if connection is old (simplified check)
                conn_age = getattr(conn, '_conn_age', 0)
                if conn_age > conn_max_age:
                    conn.close_if_unusable_or_obsolete()
                    results['connections_closed'] += 1
                    
                    # Reopen if needed
                    if conn.connection is None:
                        conn.ensure_connection()
                        results['connections_reopened'] += 1
            
            # Run VACUUM ANALYZE for PostgreSQL (during maintenance windows)
            if conn.vendor == 'postgresql' and settings.DEBUG:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("VACUUM ANALYZE")
                        results['vacuum_performed'] = True
                except Exception as e:
                    results['errors'].append(f"VACUUM failed: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to optimize connections for {alias}: {e}")
            results['errors'].append(str(e))
            return results
    
    def get_all_connections_health(self) -> List[Dict[str, Any]]:
        """
        Get health status for all database connections.
        
        Returns:
            List of health check results for each connection
        """
        health_checks = []
        for alias in connections:
            health = self.check_connection_health(alias)
            health_checks.append(health)
        
        return health_checks


# Global monitor instance
db_monitor = DatabaseMonitor()


def monitor_database_performance():
    """
    Decorator to monitor database performance of a function.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            query_count_before = len(connection.queries) if hasattr(connection, 'queries') else 0
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time
                
                query_count_after = len(connection.queries) if hasattr(connection, 'queries') else 0
                queries_executed = query_count_after - query_count_before
                
                # Log if performance is poor
                if duration > db_monitor.slow_query_threshold:
                    logger.warning(
                        f"Slow database operation in {func.__name__}: "
                        f"{duration:.3f}s, {queries_executed} queries"
                    )
                
                # Update stats
                stats = db_monitor.connection_stats['default']
                stats['queries'] += queries_executed
                stats['query_time'] += duration
                stats['last_check'] = end_time
        
        return wrapper
    return decorator


def get_database_metrics() -> Dict[str, Any]:
    """
    Get comprehensive database metrics for monitoring.
    
    Returns:
        Dictionary with database metrics
    """
    metrics = {
        'timestamp': time.time(),
        'connections': {},
        'health': {},
        'performance': {},
    }
    
    # Check all connections
    for alias in connections:
        metrics['connections'][alias] = db_monitor.get_connection_info(alias)
        metrics['health'][alias] = db_monitor.check_connection_health(alias)
        metrics['performance'][alias] = db_monitor.get_query_stats(alias)
    
    # Overall health status
    all_healthy = all(h['status'] == 'healthy' for h in metrics['health'].values())
    metrics['overall_status'] = 'healthy' if all_healthy else 'unhealthy'
    
    # Total queries across all connections
    total_queries = sum(
        p.get('total_queries', 0) 
        for p in metrics['performance'].values() 
        if isinstance(p, dict)
    )
    metrics['total_queries'] = total_queries
    
    return metrics