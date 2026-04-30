#!/bin/bash
# Backup script for CMS project
# Backs up PostgreSQL database and media files

set -e

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Defaults
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_NAME="${DB_NAME:-cms_project}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
MEDIA_DIR="./media"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
echo "Backing up database $DB_NAME..."
PGPASSWORD="${DB_PASSWORD}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --format=custom --file="$BACKUP_DIR/db_$TIMESTAMP.dump"

# Media backup
if [ -d "$MEDIA_DIR" ]; then
    echo "Backing up media directory..."
    tar -czf "$BACKUP_DIR/media_$TIMESTAMP.tar.gz" "$MEDIA_DIR"
else
    echo "Media directory not found, skipping."
fi

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/db_$TIMESTAMP.dump"
if [ -f "$BACKUP_DIR/media_$TIMESTAMP.tar.gz" ]; then
    echo "Media backup: $BACKUP_DIR/media_$TIMESTAMP.tar.gz"
fi