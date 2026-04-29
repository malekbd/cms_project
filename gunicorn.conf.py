# /home/cmsuser/cms_project/gunicorn.conf.py

bind = "unix:/home/cmsuser/cms_project/cms.sock"

workers = 3
worker_class = "sync"
timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "/home/cmsuser/cms_project/logs/gunicorn-access.log"
errorlog = "/home/cmsuser/cms_project/logs/gunicorn-error.log"
loglevel = "info"

capture_output = True
enable_stdio_inheritance = True

umask = 0o007

preload_app = False
max_requests = 1000
max_requests_jitter = 100