# Enhanced Gunicorn configuration for CMS project
# /home/cmsuser/cms_project/gunicorn.conf.py

import multiprocessing
import os

# Server socket
bind = "unix:/home/cmsuser/cms_project/cms.sock"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = "cms_gunicorn"

# Server mechanics
daemon = False
pidfile = "/home/cmsuser/cms_project/gunicorn.pid"
umask = 0o007
user = "cmsuser"
group = "cmsuser"
tmp_upload_dir = "/tmp"

# Logging
accesslog = "/home/cmsuser/cms_project/logs/gunicorn-access.log"
errorlog = "/home/cmsuser/cms_project/logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# Process management
preload_app = True
reload = False
reload_engine = "auto"
check_config = False
print_config = False

# SSL (uncomment if using SSL)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"
# ssl_version = "TLS"
# cert_reqs = 0
# ca_certs = None
# suppress_ragged_eofs = True
# do_handshake_on_connect = False

# Environment variables
raw_env = [
    "DJANGO_SETTINGS_MODULE=cms_project.settings",
    "PYTHONPATH=/home/cmsuser/cms_project",
]

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting CMS Gunicorn server")

def on_reload(server):
    """Called to recycle workers during a reload."""
    server.log.info("Reloading Gunicorn workers")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info(f"Gunicorn server is ready. Listening on: {server.address}")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    server.log.info("Shutting down Gunicorn server")

# Worker hooks
def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    worker.log.info("Worker received ABRT signal")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"Starting request: {req.method} {req.path}")
    req.start_time = time.time()

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    duration = time.time() - getattr(req, 'start_time', time.time())
    worker.log.debug(f"Finished request: {req.method} {req.path} ({duration:.3f}s)")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(f"Worker exited (pid: {worker.pid})")

# Import time for timing
import time