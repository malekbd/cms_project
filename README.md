# FRC CMS — Ticket Management System

Internal customer support and new user tracking platform for FRC.

## Tech Stack
- Django 6.0.4, PostgreSQL, Gunicorn, Nginx
- Python 3.12, python-decouple

## Setup

```bash
git clone ...
cd cms_project
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python manage.py migrate
python manage.py createsuperuser
Get-Content tickets/seed_config.py | python manage.py shell
python manage.py collectstatic
```

## Deployment
See `DEPLOYMENT_GUIDE.md`