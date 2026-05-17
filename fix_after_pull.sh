#!/bin/bash
# Quick-fix script: run after `git pull` as root to fix ownership and restart service
# Usage: sudo bash fix_after_pull.sh

set -e

PROJECT_DIR="/home/cmsuser/cms_project"
SERVICE="cms"

echo "=== Fixing file ownership after git pull ==="
echo "1. Setting project ownership to cmsuser:cmsuser..."
chown -R cmsuser:cmsuser "$PROJECT_DIR"

echo "2. Setting logs/ ownership to cmsuser:www-data..."
chown -R cmsuser:www-data "$PROJECT_DIR/logs" 2>/dev/null || true

echo "3. Setting media/ ownership to cmsuser:www-data..."
chown -R cmsuser:www-data "$PROJECT_DIR/media" 2>/dev/null || true

echo "4. Setting staticfiles/ ownership to cmsuser:www-data..."
chown -R cmsuser:www-data "$PROJECT_DIR/staticfiles" 2>/dev/null || true

echo "5. Setting permissions on logs/..."
chmod -R 755 "$PROJECT_DIR/logs" 2>/dev/null || true

echo "6. Clearing stale Python bytecode..."
su -s /bin/bash cmsuser -c "find $PROJECT_DIR -name '*.pyc' -delete && find $PROJECT_DIR -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true"

echo "7. Testing Django imports as cmsuser..."
su -s /bin/bash cmsuser -c "cd $PROJECT_DIR && ./venv/bin/python -c 'import django; django.setup(); print(\"Django OK\")'"

echo "8. Running Django system checks..."
su -s /bin/bash cmsuser -c "cd $PROJECT_DIR && ./venv/bin/python manage.py check --deploy 2>&1 | head -30"

echo "9. Restarting cms service..."
systemctl daemon-reload
systemctl restart "$SERVICE"

echo ""
echo "=== Service Status ==="
systemctl status "$SERVICE" --no-pager -l

echo ""
echo "=== Done! Service should be running. ==="