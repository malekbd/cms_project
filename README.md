# FRC CMS — Ticket Management System

Internal customer support and new user tracking platform for FRC.

## Tech Stack
- Django 6.0.4, PostgreSQL, Gunicorn, Nginx
- Python 3.12, python-decouple
- GitHub Actions for CI/CD
- Redis for caching and sessions

## Features
- Ticket management system
- User tracking and reporting
- Admin panel with Jazzmin
- Automated CI/CD pipeline
- Security hardening and monitoring

## Setup

```bash
git clone ...
cd cms_project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python manage.py migrate
python manage.py createsuperuser
Get-Content tickets/seed_config.py | python manage.py shell
python manage.py collectstatic
```

## CI/CD Pipeline

This project includes automated CI/CD pipelines using GitHub Actions:

### Continuous Integration (CI)
- **Location**: `.github/workflows/ci.yml`
- **Triggers**: Push to `main`/`develop` branches and pull requests
- **Jobs**:
  - Test: Runs Django tests with Python 3.10, 3.11, 3.12
  - Lint: Code formatting, import sorting, style checks
  - Security: Bandit and Safety vulnerability scanning
  - Build: Creates deployment package

### Continuous Deployment (CD)
- **Location**: `.github/workflows/deploy.yml`
- **Triggers**: Push to `main` branch or manual trigger
- **Features**:
  - Zero-downtime deployments
  - Automatic backups before deployment
  - Health checks and automatic rollback
  - Multi-environment support (staging/production)

### Quick Start for CI/CD
1. **Configure GitHub Secrets** in repository settings:
   - `SERVER_IP`: Production server IP
   - `SERVER_USER`: SSH username
   - `SSH_PRIVATE_KEY`: SSH private key
   - (Optional) `STAGING_SERVER_IP`: Staging server IP

2. **Push to GitHub** to trigger CI workflow
3. **Monitor deployments** in GitHub Actions tab

### Testing the Setup
```bash
# Run validation test
python test_cicd_setup.py

# Test deployment script (dry run)
./deploy.sh --dry-run
```

## Documentation
- `CD_CI_SETUP.md` - Complete CI/CD setup guide
- `DEPLOYMENT_GUIDE.md` - Detailed deployment instructions
- `SECURITY_CHECKLIST.md` - Security considerations
- `PERFORMANCE_OPTIMIZATION.md` - Performance tuning

## Deployment
See `DEPLOYMENT_GUIDE.md` for detailed deployment instructions.

## Development
```bash
# Run tests
python manage.py test

# Run linting
black .
isort .
flake8 .

# Run security checks
bandit -r .
safety check
```

## License
Internal use only.
