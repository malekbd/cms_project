import os
import sys
import django
from datetime import date, timedelta

sys.path.append('d:/APPLICATION/cms_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cms_project.settings')
django.setup()

from tickets.models import Ticket
from tickets.panel_views import scope_tickets_for_user
from django.contrib.auth.models import User

user = User.objects.first()
if user:
    all_tickets = scope_tickets_for_user(Ticket.objects.all(), user)
    total = all_tickets.count()
    month_ago = date.today() - timedelta(days=30)
    month_count = all_tickets.filter(date__gte=month_ago).count()
    print('Total:', total)
    print('Month count:', month_count)
    print('Are they equal?', total == month_count)
else:
    print('No user found')