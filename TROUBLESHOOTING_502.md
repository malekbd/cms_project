# Troubleshooting 502 Bad Gateway Error

## Problem
You're getting a 502 Bad Gateway error when accessing the CMS application.

## Root Causes
A 502 error means the web server (Nginx/Apache) cannot communicate with the backend application server (Gunicorn).

## Quick Diagnostics

### 1. Check if Gunicorn is running
**On Linux:**
```bash
systemctl status cms
ps aux | grep gunicorn
```

**On Windows:**
```cmd
tasklist | findstr gunicorn
```

### 2. Check application logs
```bash
# Gunicorn error logs
tail -f logs/gunicorn-error.log

# Django logs
tail -f logs/django.log

# Database logs  
tail -f logs/database.log
```

### 3. Check socket/port connectivity
```bash
# Check if port 8000 is listening
netstat -tlnp | grep :8000

# Check Unix socket (Linux only)
sudo ss -xlpn | grep cms.sock
ls -la /run/cms/cms.sock
```

## Common Solutions

### Solution 1: Gunicorn not starting (Windows)
**Problem:** Gunicorn has limited Windows support due to `fcntl` dependency.

**Fix:**
1. Use Django development server instead:
   ```cmd
   python manage.py runserver 127.0.0.1:8000
   ```
   
2. Or use the provided batch script:
   ```cmd
   run_server.bat
   ```

3. For production on Windows, use waitress:
   ```cmd
   pip install waitress
   waitress-serve --port=8000 cms_project.wsgi:application
   ```

### Solution 2: Socket file issues (Linux)
**Problem:** Unix socket doesn't exist or has wrong permissions.

**Fix:**
1. Check the app service logs first:
   ```bash
   sudo systemctl status cms --no-pager -l
   sudo journalctl -u cms -n 100 --no-pager
   tail -n 100 /home/cmsuser/cms_project/logs/gunicorn-error.log
   ```

2. Remove any stale project-root socket from older deployments:
   ```bash
   sudo rm -f /home/cmsuser/cms_project/cms.sock
   ```

3. Make sure Nginx proxies to the runtime socket:
   ```nginx
   location / {
       proxy_pass http://unix:/run/cms/cms.sock;
   }
   ```

4. Restart services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart cms
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. If your Nginx worker user is not `www-data`, set `Group=` in `cms.service` and `GUNICORN_GROUP`/`group` in `gunicorn.conf.py` to the actual Nginx group.

**Legacy project-root socket fallback:**
If you must keep `/home/cmsuser/cms_project/cms.sock`, the service needs write access to the project root, because Gunicorn must create and remove the socket file:
   ```bash
   sudo systemctl edit cms
   ```
   Add:
   ```ini
   [Service]
   ProtectHome=read-only
   ReadWritePaths=/home/cmsuser/cms_project
   ```
   Then:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart cms
   sudo nginx -t && sudo systemctl reload nginx
   ```

### Solution 3: Database connection issues
**Problem:** Database is not accessible.

**Fix:**
1. Check database settings in `.env`:
   ```bash
   cat .env | grep DB_
   ```

2. Test database connection:
   ```bash
   python manage.py check --database default
   ```

3. Run migrations if needed:
   ```bash
   python manage.py migrate
   ```

### Solution 4: Nginx configuration issues
**Problem:** Nginx cannot connect to Gunicorn.

**Fix:**
1. Check Nginx error log:
   ```bash
   tail -f /var/log/nginx/error.log
   ```

2. Verify Nginx configuration:
   ```bash
   sudo nginx -t
   ```

3. Check Nginx site config points to correct socket/port:
   ```bash
   cat /etc/nginx/sites-available/cms
   ```
   
   Should have:
   ```nginx
   location / {
       proxy_pass http://unix:/run/cms/cms.sock;
       # or for TCP: proxy_pass http://127.0.0.1:8000;
   }
   ```

## Prevention

### For Development (Windows):
- Use `run_server.bat` for easy startup
- Consider using WSL2 for Linux-like environment

### For Production (Linux):
1. **Monitor services:**
   ```bash
   sudo systemctl enable cms
   sudo systemctl enable nginx
   ```

2. **Set up logging:**
   ```bash
   # Rotate logs
   sudo logrotate /etc/logrotate.d/cms
   ```

3. **Health checks:**
   ```bash
   # Add to deploy.sh
   curl -f http://127.0.0.1:8000/health/ || exit 1
   ```

## Emergency Recovery

If 502 occurs in production:

1. **Immediate rollback:**
   ```bash
   ./deploy.sh --rollback
   ```

2. **Restart services:**
   ```bash
   sudo systemctl restart cms
   sudo systemctl restart nginx
   ```

3. **Fallback to development server (temporary):**
   ```bash
   # Stop Gunicorn
   sudo systemctl stop cms
   
   # Start Django dev server on port 8001
   nohup python manage.py runserver 127.0.0.1:8001 &
   
   # Update Nginx to proxy to 8001
   sudo sed -i 's/8000/8001/g' /etc/nginx/sites-available/cms
   sudo systemctl reload nginx
   ```

## Created Files for Help

1. `fix_502.py` - Diagnostic tool for 502 errors
2. `run_server.bat` - Windows batch script to start server
3. `gunicorn_local.conf.py` - Windows-compatible Gunicorn config
4. This troubleshooting guide

## Need More Help?

Run the diagnostic tool:
```bash
python fix_502.py
```

Check the deployment guide:
- `DEPLOYMENT_GUIDE.md`
- `AUTOMATIC_DEPLOYMENT_GUIDE.md`
