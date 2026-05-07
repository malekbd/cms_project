# CMS Project Deployment Summary

## Quick Deployment Steps

### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3-pip python3-venv nginx postgresql postgresql-contrib redis-server -y

# Create project user
sudo adduser cmsuser
sudo usermod -aG sudo cmsuser
su - cmsuser
```

### 2. Deploy Application
```bash
# Clone/upload project to /home/cmsuser/cms_project
cd /home/cmsuser
git clone <your-repo-url> cms_project

# Setup virtual environment
cd cms_project
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Configuration
```bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE cms_project;
CREATE USER cmsuser WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE cms_project TO cmsuser;
\q

# Update .env file with production settings
nano .env
```
Production .env example:
```
SECRET_KEY=your-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=cms.frcbd.net,103.111.122.13,localhost
DB_NAME=cms_project
DB_USER=cmsuser
DB_PASSWORD=strong_password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Django Setup
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### 5. Gunicorn Setup
```bash
# Copy service file
sudo cp cms.service /etc/systemd/system/

# Start and enable service
sudo systemctl daemon-reload
sudo systemctl start cms
sudo systemctl enable cms
sudo systemctl status cms
```

### 6. Nginx Configuration
```bash
# Create nginx config
sudo nano /etc/nginx/sites-available/cms_project
```

Nginx configuration:
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
        proxy_pass http://unix:/run/cms/cms.sock;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/cms_project /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

### 7. SSL Certificate (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d cms.frcbd.net

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 8. Security Hardening
```bash
# Firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# File permissions
sudo chown -R cmsuser:www-data /home/cmsuser/cms_project
sudo chmod -R 755 /home/cmsuser/cms_project
```

## Automated Deployment

Use the provided deployment script:
```bash
# Make executable
chmod +x deploy.sh

# Run deployment
./deploy.sh production

# Options
./deploy.sh production --force    # Force deployment
./deploy.sh production --rollback # Rollback to previous version
```

## Backup and Restore

### Backup
```bash
./backup.sh
```

### Restore
```bash
./restore.sh <backup_file>
```

## Monitoring and Maintenance

### Check Service Status
```bash
sudo systemctl status cms
sudo systemctl status nginx
sudo systemctl status postgresql
```

### View Logs
```bash
# Django logs
tail -f /home/cmsuser/cms_project/logs/django.log

# Gunicorn logs
tail -f /home/cmsuser/cms_project/logs/gunicorn-access.log
tail -f /home/cmsuser/cms_project/logs/gunicorn-error.log

# Nginx logs
tail -f /var/log/nginx/error.log

# System logs
sudo journalctl -u cms -f
```

### Update Application
```bash
cd /home/cmsuser/cms_project
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart cms
```

## Troubleshooting

### 502 Bad Gateway
```bash
sudo systemctl restart cms
sudo systemctl restart nginx
```

### Database Issues
```bash
sudo systemctl restart postgresql
python manage.py check --database default
```

### Static Files Not Loading
```bash
python manage.py collectstatic --noinput
sudo chown -R cmsuser:www-data /home/cmsuser/cms_project/staticfiles
```

## Production Checklist
- [ ] SSL certificate installed and valid
- [ ] Domain pointing correctly to server IP
- [ ] Database configured and migrated
- [ ] Static files collected and accessible
- [ ] Security headers enabled (DEBUG=False)
- [ ] Firewall configured
- [ ] Backup strategy implemented
- [ ] Monitoring setup
- [ ] Email functionality tested

## Important Notes
1. The project is configured for domain `cms.frcbd.net` and IP `103.111.122.13`
2. Update these in nginx config and ALLOWED_HOSTS if using different domain/IP
3. Production requires DEBUG=False in .env file
4. Use strong passwords for database and Django secret key
5. Regular backups are essential - use cron jobs for automation

## Support
- Full documentation: `DEPLOYMENT_GUIDE.md`
- Deployment script: `deploy.sh`
- Backup script: `backup.sh`
- Restore script: `restore.sh`
- Service file: `cms.service`
- Gunicorn config: `gunicorn.conf.py`
