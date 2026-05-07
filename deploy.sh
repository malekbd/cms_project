#!/bin/bash
# Enhanced Deployment script for CMS project with zero-downtime deployment
# Usage: ./deploy.sh [environment] [--rollback] [--force]

set -e  # Exit on error

ENVIRONMENT=${1:-production}
ROLLBACK=false
FORCE=false
DEPLOYMENT_ID=$(date +%Y%m%d_%H%M%S)

# Parse arguments
for arg in "$@"; do
    case $arg in
        --rollback)
            ROLLBACK=true
            ;;
        --force)
            FORCE=true
            ;;
    esac
done

PROJECT_DIR="/home/cmsuser/cms_project"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
BACKUP_DIR="$PROJECT_DIR/backups"
DEPLOYMENTS_DIR="$PROJECT_DIR/deployments"
CURRENT_LINK="$PROJECT_DIR/current"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Starting deployment for $ENVIRONMENT environment${NC}"
echo -e "${BLUE}Deployment ID: $DEPLOYMENT_ID${NC}"
echo -e "${BLUE}Rollback mode: $ROLLBACK${NC}"
echo -e "${BLUE}Force mode: $FORCE${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to log messages
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python3 is not installed"
        exit 1
    fi
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        warn "PostgreSQL client not found. Database operations may fail."
    fi
    
    # Check Redis
    if ! command -v redis-cli &> /dev/null; then
        warn "Redis client not found. Cache operations may fail."
    fi
    
    # Check project directory
    if [ ! -d "$PROJECT_DIR" ]; then
        error "Project directory $PROJECT_DIR does not exist"
        exit 1
    fi
    
    log "Prerequisites check completed"
}

# Function to create backup
create_backup() {
    log "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if command -v pg_dump &> /dev/null; then
        DB_NAME=$(grep -o "DB_NAME=[^ ]*" "$PROJECT_DIR/.env" | cut -d= -f2)
        DB_USER=$(grep -o "DB_USER=[^ ]*" "$PROJECT_DIR/.env" | cut -d= -f2)
        DB_HOST=$(grep -o "DB_HOST=[^ ]*" "$PROJECT_DIR/.env" | cut -d= -f2)
        DB_PORT=$(grep -o "DB_PORT=[^ ]*" "$PROJECT_DIR/.env" | cut -d= -f2)
        
        if [ -n "$DB_NAME" ]; then
            # Build pg_dump command with connection parameters
            PG_DUMP_CMD="pg_dump"
            [ -n "$DB_USER" ] && PG_DUMP_CMD="$PG_DUMP_CMD -U $DB_USER"
            [ -n "$DB_HOST" ] && PG_DUMP_CMD="$PG_DUMP_CMD -h $DB_HOST"
            [ -n "$DB_PORT" ] && PG_DUMP_CMD="$PG_DUMP_CMD -p $DB_PORT"
            
            # Set PGPASSWORD if DB_PASSWORD is available
            DB_PASSWORD=$(grep -o "DB_PASSWORD=[^ ]*" "$PROJECT_DIR/.env" | cut -d= -f2)
            if [ -n "$DB_PASSWORD" ]; then
                export PGPASSWORD="$DB_PASSWORD"
            fi
            
            if $PG_DUMP_CMD "$DB_NAME" > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql" 2>/dev/null; then
                log "Database backup created: $BACKUP_DIR/db_backup_$TIMESTAMP.sql"
            else
                warn "Database backup failed. Continuing without backup."
                # Remove empty backup file
                rm -f "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
            fi
            
            # Unset PGPASSWORD
            unset PGPASSWORD 2>/dev/null || true
        fi
    fi
    
    # Backup media files
    if [ -d "$PROJECT_DIR/media" ]; then
        tar -czf "$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR" media
        log "Media backup created: $BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz"
    fi
    
    # Backup logs
    if [ -d "$LOG_DIR" ]; then
        tar -czf "$BACKUP_DIR/logs_backup_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR" logs
        log "Logs backup created: $BACKUP_DIR/logs_backup_$TIMESTAMP.tar.gz"
    fi
    
    # Keep only last 10 backups
    ls -t "$BACKUP_DIR/"*.sql 2>/dev/null | tail -n +11 | xargs -r rm --
    ls -t "$BACKUP_DIR/"*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm --
}

# Function to update code
update_code() {
    log "Updating code..."
    
    cd "$PROJECT_DIR"
    
    # Pull latest code (if using git)
    if [ -d ".git" ]; then
        git pull origin main
        log "Code updated via git"
    else
        warn "Not a git repository. Manual code update required."
    fi
}

# Function to setup virtual environment
setup_venv() {
    log "Setting up virtual environment..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        log "Virtual environment created"
    fi
    
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r requirements.txt
    log "Dependencies installed"
}

# Function to run database migrations
run_migrations() {
    log "Running database migrations..."
    
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    python manage.py migrate --noinput
    log "Migrations completed"
}

# Function to collect static files
collect_static() {
    log "Collecting static files..."
    
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    python manage.py collectstatic --noinput --clear
    log "Static files collected"
}

# Function to run tests
run_tests() {
    log "Running tests..."
    
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        python manage.py test --noinput
        log "Tests completed"
    else
        warn "Skipping tests in $ENVIRONMENT environment"
    fi
}

# Function to restart services
restart_services() {
    log "Restarting services..."
    
    # Restart Gunicorn
    if systemctl is-active --quiet cms.service; then
        sudo systemctl restart cms.service
        log "Gunicorn service restarted"
    else
        warn "CMS service not running or not configured"
    fi
    
    # Restart Nginx
    if systemctl is-active --quiet nginx; then
        sudo systemctl reload nginx
        log "Nginx reloaded"
    fi
    
    # Restart Redis if installed
    if systemctl is-active --quiet redis-server; then
        sudo systemctl restart redis-server
        log "Redis restarted"
    fi
}

# Function to run health checks
run_health_checks() {
    log "Running health checks..."
    
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Check database connection using Django's check command
    log "Checking database connection..."
    if python manage.py check --database default 2>/dev/null; then
        log "Database connection check passed"
    else
        error "Database connection check failed"
        # Try to get more details
        python manage.py check --database default 2>&1 | head -20
        exit 1
    fi
    
    # Check if services are running
    log "Checking service status..."
    if systemctl is-active --quiet cms.service; then
        log "CMS service is running"
        
        # Try to call health endpoint via curl if available
        if command -v curl &> /dev/null; then
            if curl -f -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8000/health/ 2>/dev/null | grep -q "200"; then
                log "Health endpoint responded with 200 OK"
            else
                warn "Health endpoint not responding with 200 OK (service might still be starting)"
            fi
        else
            warn "curl not available, skipping health endpoint check"
        fi
    else
        warn "CMS service is not running (may be normal during deployment)"
    fi
    
    log "Health checks completed"
}

# Function to setup deployment directory structure
setup_deployment_structure() {
    log "Setting up deployment structure..."
    
    mkdir -p "$DEPLOYMENTS_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"
    
    # Create current symlink if it doesn't exist
    if [ ! -L "$CURRENT_LINK" ]; then
        ln -sf "$PROJECT_DIR" "$CURRENT_LINK"
    fi
}

# Function to create new deployment snapshot
create_deployment_snapshot() {
    log "Creating deployment snapshot..."
    
    DEPLOYMENT_SNAPSHOT="$DEPLOYMENTS_DIR/$DEPLOYMENT_ID"
    mkdir -p "$DEPLOYMENT_SNAPSHOT"
    
    # Copy project files (excluding venv, logs, backups, deployments)
    rsync -av --exclude='venv' --exclude='logs' --exclude='backups' --exclude='deployments' \
          --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' \
          "$PROJECT_DIR/" "$DEPLOYMENT_SNAPSHOT/"
    
    log "Deployment snapshot created: $DEPLOYMENT_SNAPSHOT"
}

# Function to switch to new deployment (zero-downtime)
switch_deployment() {
    log "Switching to new deployment..."
    
    # Update current symlink atomically
    # Use a temporary file in /tmp to avoid conflict with symlink resolution
    TMP_LINK="/tmp/cms_current_$DEPLOYMENT_ID.tmp"
    ln -sfn "$DEPLOYMENTS_DIR/$DEPLOYMENT_ID" "$TMP_LINK"
    mv -f "$TMP_LINK" "$CURRENT_LINK"
    
    log "Deployment switched to $DEPLOYMENT_ID"
}

# Function to rollback to previous deployment
rollback_deployment() {
    log "Initiating rollback..."
    
    # Find previous deployment
    PREVIOUS_DEPLOYMENT=$(ls -t "$DEPLOYMENTS_DIR" | head -2 | tail -1)
    
    if [ -z "$PREVIOUS_DEPLOYMENT" ]; then
        error "No previous deployment found for rollback"
        exit 1
    fi
    
    log "Rolling back to deployment: $PREVIOUS_DEPLOYMENT"
    
    # Switch to previous deployment
    TMP_LINK="/tmp/cms_current_rollback_$PREVIOUS_DEPLOYMENT.tmp"
    ln -sfn "$DEPLOYMENTS_DIR/$PREVIOUS_DEPLOYMENT" "$TMP_LINK"
    mv -f "$TMP_LINK" "$CURRENT_LINK"
    
    # Restart services
    restart_services
    
    log "Rollback completed to $PREVIOUS_DEPLOYMENT"
}

# Function to perform canary deployment (gradual rollout)
canary_deployment() {
    log "Starting canary deployment..."
    
    # Phase 1: Deploy to 10% of traffic (simulated)
    log "Phase 1: Deploying to 10% of traffic"
    switch_deployment
    
    # Wait and monitor
    sleep 30
    run_health_checks
    
    # Phase 2: Deploy to 50% of traffic
    log "Phase 2: Deploying to 50% of traffic"
    # In a real scenario, you would update load balancer weights here
    
    # Wait and monitor
    sleep 30
    run_health_checks
    
    # Phase 3: Full deployment
    log "Phase 3: Full deployment (100% of traffic)"
    
    log "Canary deployment completed"
}

# Function to run comprehensive tests
run_comprehensive_tests() {
    log "Running comprehensive tests..."
    
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Run unit tests
    python manage.py test tickets --noinput
    
    # Run integration tests if available
    if [ -f "tests/integration_tests.py" ]; then
        python -m pytest tests/integration_tests.py -v
    fi
    
    # Run security tests
    if [ -f "tests/security_tests.py" ]; then
        python -m pytest tests/security_tests.py -v
    fi
    
    log "Comprehensive tests completed"
}

# Function to validate deployment
validate_deployment() {
    log "Validating deployment..."
    
    # Check if application is running
    if curl -s -f http://localhost:8000/health/liveness/ > /dev/null; then
        log "Application is responding to health checks"
    else
        error "Application is not responding after deployment"
        return 1
    fi
    
    # Check database connectivity
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    
    if python manage.py check --database default 2>/dev/null; then
        log "Database connectivity validated"
    else
        error "Database connectivity check failed"
        return 1
    fi
    
    # Check cache connectivity
    if python -c "
from django.core.cache import cache
cache.set('validation_test', 'ok', 1)
result = cache.get('validation_test')
print('Cache test:', 'passed' if result == 'ok' else 'failed')
" 2>/dev/null | grep -q "passed"; then
        log "Cache connectivity validated"
    else
        warn "Cache connectivity check failed"
    fi
    
    log "Deployment validation completed successfully"
    return 0
}

# Function to clean up old deployments
cleanup_old_deployments() {
    log "Cleaning up old deployments..."
    
    # Keep last 5 deployments
    DEPLOYMENT_COUNT=$(ls -1 "$DEPLOYMENTS_DIR" | wc -l)
    
    if [ "$DEPLOYMENT_COUNT" -gt 5 ]; then
        OLD_DEPLOYMENTS=$(ls -t "$DEPLOYMENTS_DIR" | tail -n +6)
        
        for OLD_DEPLOYMENT in $OLD_DEPLOYMENTS; do
            log "Removing old deployment: $OLD_DEPLOYMENT"
            rm -rf "$DEPLOYMENTS_DIR/$OLD_DEPLOYMENT"
        done
        
        log "Cleaned up $((DEPLOYMENT_COUNT - 5)) old deployments"
    else
        log "No old deployments to clean up"
    fi
}

# Function to clean up
cleanup() {
    log "Cleaning up..."
    
    cd "$PROJECT_DIR"
    
    # Remove Python cache files
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    
    # Clear cache if Redis is available
    if command -v redis-cli &> /dev/null; then
        redis-cli FLUSHALL 2>/dev/null || true
    fi
    
    log "Cleanup completed"
}

# Function to monitor deployment
monitor_deployment() {
    log "Monitoring deployment..."
    
    # Wait a bit for services to start
    sleep 5
    
    # Check service status
    if systemctl is-active --quiet cms.service; then
        log "CMS service is running"
    else
        error "CMS service is not running"
        exit 1
    fi
    
    # Check Nginx
    if systemctl is-active --quiet nginx; then
        log "Nginx is running"
    else
        error "Nginx is not running"
        exit 1
    fi
    
    log "Deployment monitoring completed"
}

# Enhanced main deployment process with zero-downtime
main() {
    log "Starting enhanced deployment process for CMS project"
    
    # Check if we're in rollback mode
    if [ "$ROLLBACK" = true ]; then
        rollback_deployment
        validate_deployment
        log "${GREEN}Rollback completed successfully!${NC}"
        exit 0
    fi
    
    # Setup deployment structure
    setup_deployment_structure
    
    # Phase 1: Preparation
    log "${BLUE}=== Phase 1: Preparation ===${NC}"
    check_prerequisites
    create_backup
    update_code
    
    # Create deployment snapshot
    create_deployment_snapshot
    
    # Phase 2: Build and Test
    log "${BLUE}=== Phase 2: Build and Test ===${NC}"
    setup_venv
    run_migrations
    collect_static
    
    # Run tests based on environment
    if [ "$ENVIRONMENT" = "production" ] && [ "$FORCE" = false ]; then
        run_comprehensive_tests
    else
        run_tests
    fi
    
    # Phase 3: Deployment
    log "${BLUE}=== Phase 3: Deployment ===${NC}"
    
    # Choose deployment strategy based on environment
    if [ "$ENVIRONMENT" = "production" ] && [ "$FORCE" = false ]; then
        # Canary deployment for production
        canary_deployment
    else
        # Standard deployment for staging/development
        switch_deployment
        restart_services
    fi
    
    # Phase 4: Validation
    log "${BLUE}=== Phase 4: Validation ===${NC}"
    monitor_deployment
    run_health_checks
    
    if ! validate_deployment; then
        error "Deployment validation failed"
        
        # Auto-rollback on validation failure (unless forced)
        if [ "$FORCE" = false ]; then
            warn "Initiating automatic rollback due to validation failure"
            rollback_deployment
            error "Deployment failed and was rolled back"
            exit 1
        else
            warn "Force mode enabled - continuing despite validation failure"
        fi
    fi
    
    # Phase 5: Cleanup
    log "${BLUE}=== Phase 5: Cleanup ===${NC}"
    cleanup
    cleanup_old_deployments
    
    log "${GREEN}========================================${NC}"
    log "${GREEN}Deployment completed successfully!${NC}"
    log "${GREEN}Deployment ID: $DEPLOYMENT_ID${NC}"
    log "${GREEN}Environment: $ENVIRONMENT${NC}"
    log "${GREEN}Timestamp: $TIMESTAMP${NC}"
    log "${GREEN}========================================${NC}"
    
    # Send deployment notification (optional)
    send_deployment_notification
}

# Function to send deployment notification
send_deployment_notification() {
    # This is a placeholder for deployment notifications
    # Could integrate with Slack, Email, or other notification systems
    log "Deployment notification would be sent here"
    
    # Example Slack notification (commented out)
    # curl -X POST -H 'Content-type: application/json' \
    # --data "{\"text\":\"Deployment $DEPLOYMENT_ID completed for $ENVIRONMENT environment\"}" \
    # https://example.slack.webhook.url/...
}

# Error handling wrapper
run_with_error_handling() {
    set +e  # Disable exit on error for the trap
    
    # Set up error trap
    trap 'error "Deployment failed at line $LINENO"; exit 1' ERR
    
    # Run main function
    main "$@"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        return 0
    else
        error "Deployment failed with exit code $exit_code"
        
        # Attempt rollback on failure (unless already in rollback or forced)
        if [ "$ROLLBACK" = false ] && [ "$FORCE" = false ]; then
            warn "Attempting emergency rollback..."
            if rollback_deployment; then
                error "Emergency rollback completed"
            else
                error "Emergency rollback failed"
            fi
        fi
        
        exit $exit_code
    fi
}

# Run with error handling
run_with_error_handling "$@"