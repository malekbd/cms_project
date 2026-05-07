# CD/CI Setup for CMS Project

This document describes the Continuous Integration and Continuous Deployment setup for the CMS project.

## Overview

The project uses GitHub Actions for both CI (Continuous Integration) and CD (Continuous Deployment). The setup includes:

1. **CI Pipeline**: Runs on every push and pull request to `main` and `develop` branches
2. **CD Pipeline**: Deploys to production when CI passes on `main` branch
3. **Manual Deployment**: Supports manual deployment to different environments

## Workflows

### 1. CI Pipeline (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests targeting `main` or `develop`
- Weekly security scan (Sundays at midnight UTC)

**Jobs:**
- **Test**: Runs Django tests with multiple Python versions (3.10, 3.11, 3.12)
- **Lint**: Code formatting, import sorting, and style checks
- **Security**: Security scanning with Bandit and Safety
- **Build**: Creates deployment package (only on main branch)
- **Notify**: Sends notifications on failure

### 2. CD Pipeline (`.github/workflows/deploy.yml`)

**Triggers:**
- Push to `main` branch (auto-deploy to production)
- Manual trigger via GitHub UI with environment selection

**Jobs:**
- **Pre-deploy checks**: Validates deployment readiness
- **Deploy**: Executes deployment via SSH to target server
- **Post-deploy**: Generates deployment report

### 3. Advanced CD Pipeline (`.github/workflows/cd.yml`)

**Triggers:**
- After successful CI run on `main` branch

**Features:**
- Zero-downtime deployments
- Automatic rollback on failure
- Deployment version tagging
- Multi-environment support (staging/production)

## Required GitHub Secrets

The following secrets must be configured in your GitHub repository settings:

### Essential Secrets
| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SERVER_IP` | Production server IP address | `192.168.1.100` |
| `SERVER_USER` | SSH username for deployment | `cmsuser` |
| `SSH_PRIVATE_KEY` | SSH private key for authentication | `-----BEGIN RSA PRIVATE KEY-----...` |
| `STAGING_SERVER_IP` | (Optional) Staging server IP | `192.168.1.101` |

### Optional Secrets
| Secret Name | Description | When to Use |
|-------------|-------------|-------------|
| `SLACK_WEBHOOK_URL` | Webhook for Slack notifications | For deployment notifications |
| `CODECOV_TOKEN` | Code coverage upload token | If using Codecov |
| `DATABASE_URL` | Production database URL | If not using SQLite |

## Server Configuration

### Prerequisites
1. Python 3.10+ installed
2. Git installed
3. Systemd services configured:
   - `gunicorn` (application server)
   - `nginx` (web server)
   - `cms` (custom service if any)
4. SSH access with key authentication
5. Proper directory structure at `/home/cmsuser/cms_project/`

### Directory Structure on Server
```
/home/cmsuser/cms_project/
├── current/ -> deployments/20250101_120000/ (symlink)
├── deployments/
│   └── 20250101_120000/
│       ├── venv/
│       ├── manage.py
│       └── ...
├── backups/
│   └── production_20250101_120000/
├── logs/
├── .env
└── db.sqlite3
```

## Environment Variables

### Application (.env file)
Create a `.env` file on the server with:

```bash
# Django Settings
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=your-domain.com,localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3
# or for PostgreSQL: postgres://user:password@localhost/dbname

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### GitHub Actions Environment
The workflows use the following environment variables:

```yaml
env:
  DEPLOYMENT_ENV: production
  PROJECT_PATH: /home/cmsuser/cms_project
```

## Deployment Process

### Automatic Deployment (Main Branch)
1. Developer pushes to `main` branch
2. CI pipeline runs tests, linting, security checks
3. If CI passes, CD pipeline triggers automatically
4. Deployment process:
   - Creates backup of current deployment
   - Pulls latest code
   - Installs/updates dependencies
   - Runs database migrations
   - Collects static files
   - Restarts services
   - Performs health check

### Manual Deployment
1. Go to GitHub Actions → "Deploy to Server" workflow
2. Click "Run workflow"
3. Select environment (production/staging)
4. Optionally enable force deployment
5. Monitor deployment progress

### Rollback Process
If deployment fails:
1. Automatic rollback attempts to restore from latest backup
2. Manual rollback available via:
   ```bash
   cd /home/cmsuser/cms_project
   ./deploy.sh --rollback
   ```

## Testing the Setup

### 1. Test CI Pipeline Locally
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python manage.py test

# Run linting
black --check .
isort --check-only .
flake8 .

# Run security checks
bandit -r .
safety check
```

### 2. Test Deployment Script
```bash
# Dry run of deployment script
./deploy.sh --dry-run

# Test with specific environment
./deploy.sh staging
```

### 3. Verify GitHub Actions
1. Push a test commit to `develop` branch
2. Check GitHub Actions tab for CI run
3. Verify all jobs pass
4. Merge to `main` and verify CD triggers

## Monitoring and Troubleshooting

### Logs Location
- **GitHub Actions**: `.github/workflows/` logs in GitHub UI
- **Server**: `/home/cmsuser/cms_project/logs/`
- **Application**: Check systemd journal:
  ```bash
  journalctl -u gunicorn -f
  journalctl -u nginx -f
  ```

### Common Issues

#### 1. SSH Connection Failed
- Verify SSH private key is correctly added to GitHub secrets
- Check server firewall allows port 2111
- Test SSH connection manually:
  ```bash
  ssh -p 2111 cmsuser@server-ip
  ```

#### 2. Permission Denied
- Ensure `cmsuser` has write permissions to project directory
- Check service user can access required files

#### 3. Database Migration Failed
- Check database connection settings
- Verify migrations are up to date locally first
- Consider adding `--fake` option for problematic migrations

#### 4. Health Check Fails
- Verify application is running: `systemctl status gunicorn`
- Check port 8000 is accessible locally
- Review application logs for errors

## Best Practices

### 1. Branch Strategy
- `main`: Production-ready code, auto-deploys to production
- `develop`: Integration branch, deploys to staging
- Feature branches: Individual features, CI runs on PR

### 2. Commit Messages
- Use conventional commits for automatic versioning
- Include `[skip ci]` in commit message to skip CI (when needed)
- Include `[skip deploy]` to skip CD

### 3. Deployment Safety
- Always test in staging before production
- Use feature flags for risky changes
- Monitor metrics after deployment
- Have rollback plan ready

### 4. Security
- Rotate SSH keys periodically
- Use environment variables for secrets
- Regular security scanning in CI
- Keep dependencies updated

## Maintenance

### Regular Tasks
1. Update dependencies: `pip install -U -r requirements.txt`
2. Review and update GitHub Actions workflows
3. Clean up old deployments and backups
4. Monitor disk usage on server

### Scaling Considerations
- Consider containerization (Docker) for consistent environments
- Implement blue-green deployments for zero downtime
- Add load balancing for multiple instances
- Implement database replication for high availability

## Support

For issues with the CD/CI setup:
1. Check GitHub Actions logs
2. Review server logs
3. Test deployment script manually
4. Consult the deployment guide in `DEPLOYMENT_GUIDE.md`

## Related Documentation
- `DEPLOYMENT_GUIDE.md` - Detailed deployment instructions
- `SECURITY_CHECKLIST.md` - Security considerations
- `PERFORMANCE_OPTIMIZATION.md` - Performance tuning
- `README.md` - Project overview