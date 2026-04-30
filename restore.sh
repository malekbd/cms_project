#!/bin/bash
# Restore script for CMS project
# Restores PostgreSQL database and media files from backup

set -e

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Defaults
BACKUP_DIR="./backups"
DB_NAME="${DB_NAME:-cms_project}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
MEDIA_DIR="./media"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_timestamp>"
    echo "Available backups:"
    ls -1 "$BACKUP_DIR"/*.dump 2>/dev/null | sed 's/.*db_//;s/\.dump//' || echo "No backups found"
    exit 1
fi

TIMESTAMP="$1"
DB_BACKUP="$BACKUP_DIR/db_$TIMESTAMP.dump"
MEDIA_BACKUP="$BACKUP_DIR/media_$TIMESTAMP.tar.gz"

if [ ! -f "$DB_BACKUP" ]; then
    echo "Database backup not found: $DB_BACKUP"
    exit 1
fi

echo "Restoring database $DB_NAME from $DB_BACKUP..."
# Drop and recreate database? For safety, we'll use pg_restore with --clean
PGPASSWORD="${DB_PASSWORD}" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists "$DB_BACKUP"

if [ -f "$MEDIA_BACKUP" ]; then
    echo "Restoring media directory..."
    # Remove existing media directory? We'll backup existing media first
    if [ -d "$MEDIA_DIR" ]; then
        mv "$MEDIA_DIR" "${MEDIA_DIR}_backup_$(date +%s)"
    fi
    tar -xzf "$MEDIA_BACKUP" -C "$(dirname "$MEDIA_DIR")"
    echo "Media restored. Old media backed up as ${MEDIA_DIR}_backup_*"
else
    echo "No media backup found, skipping."
fi

echo "Restore completed."