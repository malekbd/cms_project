# Server Deployment Guide

## Prerequisites
- Ubuntu 20.04+ or CentOS 8+ server
- Python 3.8+
- Domain pointing to server IP (cms.frcbd.net)
- SSL certificate (Let's Encrypt recommended)

## Step 1: Server Setup

### Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### Install Required Packages
```bash
sudo apt install python3-pip python3-venv nginx postgresql postgresql-contrib -y
```

### Create Project User
```bash
sudo adduser cmsuser
sudo usermod -aG sudo cmsuser
su - cmsuser
```

## Step 2: Deploy Application

### Clone/Upload Project
```bash
# Option 1: Git clone (if using git)
git clone <your-repo-url> cms_project

# Option 2: Upload files via SCP
# scp -r cms_project/ cmsuser@your-server:/home/cmsuser/
```

### Setup Virtual Environment
```bash
cd cms_project
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure Environment
```bash
# .env file should already be present
# Verify it has correct settings
cat .env
```

## Step 3: Database Setup

### PostgreSQL (Recommended for Production)
```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE cms_project;
CREATE USER cmsuser WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE cms_project TO cmsuser;
\q
```

### Update .env for PostgreSQL
```bash
# Edit .env file
DATABASE_URL=postgresql://cmsuser:strong_password@localhost/cms_project
```

### Run Migrations
```bash
python manage.py migrate
```

### Create Superuser
```bash
python manage.py createsuperuser
```

### Collect Static Files
```bash
python manage.py collectstatic --noinput
```

## Step 4: Configure Gunicorn

### Create Gunicorn Service File
```bash
sudo nano /etc/systemd/system/cms.service
```

### Service File Content:
```ini
[Unit]
Description=CMS Django Project
After=network.target

[Service]
User=cmsuser
Group=www-data
WorkingDirectory=/home/cmsuser/cms_project
Environment=PATH=/home/cmsuser/cms_project/venv/bin
ExecStart=/home/cmsuser/cms_project/venv/bin/gunicorn --workers 3 --bind unix:/home/cmsuser/cms_project/cms.sock cms_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

### Start and Enable Service
```bash
sudo systemctl start cms
sudo systemctl enable cms
sudo systemctl status cms
```

## Step 5: Configure Nginx

### Create Nginx Config
```bash
sudo nano /etc/nginx/sites-available/cms_project
```

### Nginx Config Content:
```nginx
server {
    listen 80;
    server_name cms.frcbd.net 103.111.122.13;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/cmsuser/cms_project;
    }

    location /media/ {
        root /home/cmsuser/cms_project;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/cmsuser/cms_project/cms.sock;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

### Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/cms_project /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## Step 6: SSL Certificate (Let's Encrypt)

### Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Get SSL Certificate
```bash
sudo certbot --nginx -d cms.frcbd.net -d 103.111.122.13
```

### Auto-renewal
```bash
sudo crontab -e
# Add this line:
0 12 * * * /usr/bin/certbot renew --quiet
```

## Step 7: Security Hardening

### Firewall Setup
```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### File Permissions
```bash
sudo chown -R cmsuser:www-data /home/cmsuser/cms_project
sudo chmod -R 755 /home/cmsuser/cms_project
```

### Security Headers (Already configured in Django)
- HSTS enabled
- CSRF protection
- XSS protection
- Content type options

## Step 8: Monitoring & Logging

### Setup Log Rotation
```bash
sudo nano /etc/logrotate.d/cms_project
```

### Log Rotation Config:
```
/home/cmsuser/cms_project/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 cmsuser www-data
    postrotate
        systemctl reload cms
    endscript
}
```

### Monitor Service Status
```bash
# Check service status
sudo systemctl status cms
sudo systemctl status nginx

# View logs
sudo journalctl -u cms -f
tail -f /home/cmsuser/cms_project/logs/django.log
```

## Step 9: Performance Optimization

### Gunicorn Workers
```bash
# Update workers based on CPU cores (2x cores + 1)
ExecStart=/home/cmsuser/cms_project/venv/bin/gunicorn --workers 5 --bind unix:/home/cmsuser/cms_project/cms.sock cms_project.wsgi:application
```

### Nginx Caching (Optional)
```nginx
location /static/ {
    root /home/cmsuser/cms_project;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Step 10: Backup Strategy

### Database Backup Script
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/home/cmsuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump cms_project > $BACKUP_DIR/cms_backup_$DATE.sql
find $BACKUP_DIR -name "cms_backup_*.sql" -mtime +7 -delete
```

### Automated Backup
```bash
# Add to crontab
0 2 * * * /home/cmsuser/backup.sh
```

## Testing the Deployment

1. **Check Django Admin**: `https://cms.frcbd.net/admin/`
2. **Check Panel**: `https://cms.frcbd.net/panel/`
3. **Test Login**: Use superuser credentials
4. **Test Features**: Create/edit tickets
5. **Check SSL**: Certificate should be valid

## Troubleshooting

### Common Issues:
1. **502 Bad Gateway**: Gunicorn not running
   ```bash
   sudo systemctl restart cms
   ```

2. **Static Files 404**: Check collectstatic and permissions
   ```bash
   python manage.py collectstatic --noinput
   sudo chown -R cmsuser:www-data /home/cmsuser/cms_project/staticfiles
   ```

3. **Database Connection**: Check PostgreSQL status and credentials
   ```bash
   sudo systemctl status postgresql
   ```

### Logs Location:
- Django logs: `/home/cmsuser/cms_project/logs/django.log`
- Nginx logs: `/var/log/nginx/error.log`
- System logs: `sudo journalctl -u cms`

## Production Checklist

- [ ] SSL certificate installed and valid
- [ ] Domain pointing correctly
- [ ] Database configured and migrated
- [ ] Static files collected and accessible
- [ ] Email functionality working
- [ ] Security headers enabled
- [ ] Firewall configured
- [ ] Backup strategy implemented
- [ ] Monitoring setup
- [ ] Performance optimized

## Support Commands

```bash
# Restart services
sudo systemctl restart cms nginx

# View logs
sudo journalctl -u cms -f

# Update application
cd /home/cmsuser/cms_project
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart cms
```
