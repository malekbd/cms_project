import json
import csv
import re
from datetime import date, timedelta
from calendar import month_abbr
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q, Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone

from .models import (
    Ticket, TicketRemark, STATUS_CHOICES,
    IssueType, ReceivedByOption, TechnicianOption, BranchOption, PanelBrandSettings, PartnerOption
)
from .forms import TicketForm
from .ai_reporting_agent import ReportingAIAgent


def get_current_date():
    now = timezone.now()
    return timezone.localtime(now).date() if timezone.is_aware(now) else now.date()


def get_ticket_panel_route(ticket):
    if ticket.is_partner:
        return 'panel_partner_tickets'
    if ticket.is_new_user:
        return 'panel_new_user_tracking'
    return 'panel_tickets'


def normalize_key(value):
    return re.sub(r'[^a-z0-9]+', '', (value or '').lower())


def format_branch_name(value):
    """Return a human-readable branch name for reports/UI."""
    if not value:
        return 'No Branch'

    branch = BranchOption.objects.filter(Q(name=value) | Q(display_name=value)).first()
    if branch:
        return branch.display_name or branch.name.replace('_', ' ').title()

    return str(value).replace('_', ' ').title()


def get_user_branch_scope(user):
    if not getattr(user, 'is_authenticated', False) or user.is_superuser:
        return None

    username = (user.username or '').strip().lower()
    if not username.startswith('frc-'):
        return None

    branch_key = normalize_key(username[4:])
    branches = list(BranchOption.objects.filter(is_active=True))
    for branch in branches:
        names = [branch.name, branch.display_name, branch.display_name.replace(' Branch', '')]
        if branch_key in [normalize_key(name) for name in names]:
            return branch

    for branch in branches:
        if branch_key and (
            branch_key in normalize_key(branch.name) or
            branch_key in normalize_key(branch.display_name)
        ):
            return branch

    return None


def branch_query(branch):
    return Q(branch=branch.name) | Q(branch=branch.display_name)


def apply_branch_filter(queryset, branch_value):
    if not branch_value:
        return queryset
    branch = BranchOption.objects.filter(Q(name=branch_value) | Q(display_name=branch_value)).first()
    if branch:
        return queryset.filter(branch_query(branch))
    return queryset.filter(branch=branch_value)


def scope_tickets_for_user(queryset, user):
    branch = get_user_branch_scope(user)
    if branch:
        return queryset.filter(branch_query(branch))
    return queryset


def get_visible_branch_options(user):
    branch = get_user_branch_scope(user)
    if branch:
        return BranchOption.objects.filter(pk=branch.pk)
    return BranchOption.objects.filter(is_active=True).order_by('sort_order', 'display_name')


def get_scoped_ticket_or_404(request, pk):
    return get_object_or_404(scope_tickets_for_user(Ticket.objects.all(), request.user), pk=pk)


def require_superuser(request):
    if request.user.is_superuser:
        return None
    messages.error(request, 'Superadmin access required.')
    return redirect('panel_dashboard')


def is_last_superuser(user):
    return user.is_superuser and not User.objects.filter(is_superuser=True).exclude(pk=user.pk).exists()


def build_dashboard_payload(user):
    today = get_current_date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    all_tickets = scope_tickets_for_user(Ticket.objects.all(), user)
    total = all_tickets.count()

    status_counts = {
        row['status']: row['count']
        for row in all_tickets.values('status').annotate(count=Count('sn'))
    }
    solved = status_counts.get('SOLVED', 0)
    pending = status_counts.get('PENDING', 0)
    time_taken = status_counts.get('TIME TAKEN', 0)
    no_response = status_counts.get('No Response', 0)

    today_count = all_tickets.filter(date=today).count()
    week_count = all_tickets.filter(date__gte=week_ago).count()
    month_count = all_tickets.filter(date__gte=month_ago).count()

    last_week_start = week_ago - timedelta(days=7)
    last_week_count = all_tickets.filter(date__gte=last_week_start, date__lt=week_ago).count()
    if last_week_count > 0:
        week_trend = round(((week_count - last_week_count) / last_week_count) * 100, 1)
    else:
        week_trend = 100 if week_count > 0 else 0

    solve_rate = round((solved / total * 100), 1) if total > 0 else 0

    trend_start = today - timedelta(days=13)
    daily_rows = {
        row['date']: row['count']
        for row in all_tickets.filter(date__gte=trend_start)
        .values('date')
        .annotate(count=Count('sn'))
    }
    daily_dates = [trend_start + timedelta(days=i) for i in range(14)]
    daily_labels = [day.strftime('%d %b') for day in daily_dates]
    daily_values = [daily_rows.get(day, 0) for day in daily_dates]

    top_issues = [
        {'issue': row['issue'] or 'No Issue', 'count': row['count']}
        for row in all_tickets.values('issue').annotate(count=Count('sn')).order_by('-count')[:10]
    ]
    top_technicians = list(
        all_tickets.exclude(technician_name__isnull=True)
        .exclude(technician_name='')
        .values('technician_name')
        .annotate(count=Count('sn'))
        .order_by('-count')[:10]
    )
    branch_stats = [
        {'branch': format_branch_name(row['branch']), 'count': row['count']}
        for row in all_tickets.values('branch').annotate(count=Count('sn')).order_by('-count')[:10]
    ]

    status_data = [
        {'label': 'Solved', 'value': solved, 'color': '#10b981'},
        {'label': 'Pending', 'value': pending, 'color': '#f59e0b'},
        {'label': 'Time Taken', 'value': time_taken, 'color': '#8b5cf6'},
        {'label': 'No Response', 'value': no_response, 'color': '#ef4444'},
    ]

    recent_tickets = [
        {
            'sn': ticket.sn,
            'user_name': ticket.user_name or '-',
            'issue': ticket.issue or '-',
            'status': ticket.status,
            'detail_url': reverse('panel_ticket_detail', args=[ticket.sn]),
        }
        for ticket in all_tickets.order_by('-created_at')[:10]
    ]

    return {
        'total': total,
        'solved': solved,
        'pending': pending,
        'time_taken': time_taken,
        'no_response': no_response,
        'today_count': today_count,
        'week_count': week_count,
        'month_count': month_count,
        'week_trend': week_trend,
        'solve_rate': solve_rate,
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'status_data': status_data,
        'top_issues': top_issues,
        'top_technicians': top_technicians,
        'branch_stats': branch_stats,
        'recent_tickets': recent_tickets,
        'last_updated': timezone.now().strftime('%d %b %Y %I:%M:%S %p'),
    }


# ─── Authentication ─────────────────────────────────────────────────────────

def panel_login(request):
    if request.user.is_authenticated:
        return redirect('panel_dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'panel_dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'panel/login.html')


@login_required
def panel_logout(request):
    logout(request)
    return redirect('panel_login')


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def panel_dashboard(request):
    payload = build_dashboard_payload(request.user)

    context = {
        'active_page': 'dashboard',
        **payload,
        'daily_labels': json.dumps(payload['daily_labels']),
        'daily_values': json.dumps(payload['daily_values']),
        'status_data': json.dumps(payload['status_data']),
        'top_issues': json.dumps(payload['top_issues']),
        'top_technicians': json.dumps(payload['top_technicians']),
        'branch_stats': json.dumps(payload['branch_stats']),
    }
    return render(request, 'panel/dashboard.html', context)


@login_required
def panel_dashboard_data(request):
    return JsonResponse(build_dashboard_payload(request.user))


# ─── Ticket Management ──────────────────────────────────────────────────────

@login_required
def panel_tickets(request):
    tickets_qs = scope_tickets_for_user(
        Ticket.objects.filter(is_partner=False, is_new_user=False),
        request.user,
    ).order_by('-date', '-time')

    search = request.GET.get('search', '')
    status_f = request.GET.get('status', '')
    branch_f = request.GET.get('branch', '')
    issue_f = request.GET.get('issue', '')
    tech_f = request.GET.get('technician', '')
    d_from = request.GET.get('date_from', '')
    d_to = request.GET.get('date_to', '')

    if search:
        tickets_qs = tickets_qs.filter(
            Q(user_name__icontains=search) | Q(customer_id__icontains=search) | Q(cell_no__icontains=search)
        )
    if status_f:
        tickets_qs = tickets_qs.filter(status=status_f)
    if branch_f:
        tickets_qs = apply_branch_filter(tickets_qs, branch_f)
    if issue_f:
        tickets_qs = tickets_qs.filter(issue=issue_f)
    if tech_f:
        tickets_qs = tickets_qs.filter(technician_name=tech_f)
    if d_from:
        tickets_qs = tickets_qs.filter(date__gte=d_from)
    if d_to:
        tickets_qs = tickets_qs.filter(date__lte=d_to)

    active_paginator = Paginator(tickets_qs.exclude(status='SOLVED'), 10)
    active_tickets = active_paginator.get_page(request.GET.get('page'))

    solved_paginator = Paginator(tickets_qs.filter(status='SOLVED'), 10)
    solved_tickets = solved_paginator.get_page(request.GET.get('solved_page'))

    context = {
        'active_page': 'tickets', 'active_tickets': active_tickets, 'solved_tickets': solved_tickets,
        'active_count': active_paginator.count, 'solved_count': solved_paginator.count,
        'form': TicketForm(), 'search': search, 'status_filter': status_f, 'branch_filter': branch_f,
        'issue_filter': issue_f, 'technician_filter': tech_f, 'date_from': d_from, 'date_to': d_to,
        'status_choices': STATUS_CHOICES,
        'branch_choices': get_visible_branch_options(request.user).values_list('name', 'display_name'),
        'issue_choices': IssueType.objects.filter(is_active=True).values_list('name', 'display_name'),
        'technician_choices': TechnicianOption.objects.filter(is_active=True).values_list('name', 'display_name'),
        'total_filtered': tickets_qs.count(),
    }
    return render(request, 'panel/tickets.html', context)


@login_required
def panel_partner_tickets(request):
    tickets_qs = scope_tickets_for_user(Ticket.objects.filter(is_partner=True), request.user).order_by('-date', '-time')
    search = request.GET.get('search', '')
    status_f = request.GET.get('status', '')

    if search:
        tickets_qs = tickets_qs.filter(
            Q(user_name__icontains=search) |
            Q(partner_user_name__icontains=search) |
            Q(cell_no__icontains=search)
        )
    if status_f:
        tickets_qs = tickets_qs.filter(status=status_f)

    active_paginator = Paginator(tickets_qs.exclude(status='SOLVED'), 10)
    active_tickets = active_paginator.get_page(request.GET.get('page'))

    solved_paginator = Paginator(tickets_qs.filter(status='SOLVED'), 10)
    solved_tickets = solved_paginator.get_page(request.GET.get('solved_page'))

    context = {
        'active_page': 'partners', 'active_tickets': active_tickets, 'solved_tickets': solved_tickets,
        'active_count': active_paginator.count, 'solved_count': solved_paginator.count,
        'form': TicketForm(initial={'is_partner': True}), 'search': search, 'status_filter': status_f,
        'status_choices': STATUS_CHOICES, 'total_filtered': tickets_qs.count(),
        'issue_choices': IssueType.objects.filter(is_active=True).values_list('name', 'display_name'),
    }
    return render(request, 'panel/partner_tickets.html', context)


@login_required
def panel_add_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save()
            msg = form.cleaned_data.get('remark') or f"Ticket created with status: {ticket.status}"
            TicketRemark.objects.create(ticket=ticket, status=ticket.status, remark=msg, created_by=request.user.username)
            messages.success(request, f'Ticket #{ticket.sn} created!')
        else:
            messages.error(request, 'Error creating ticket. Please check the fields.')

    is_p = request.POST.get('is_partner') == 'True'
    is_new_user = request.POST.get('is_new_user') in ['on', 'true', 'True', True]
    if is_p:
        return redirect('panel_partner_tickets')
    if is_new_user:
        return redirect('panel_new_user_tracking')
    return redirect('panel_tickets')


@login_required
def panel_edit_ticket(request, pk):
    ticket = get_scoped_ticket_or_404(request, pk)
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            updated = form.save()
            if form.cleaned_data.get('remark'):
                TicketRemark.objects.create(ticket=updated, status=updated.status, remark=form.cleaned_data.get('remark'), created_by=request.user.username)
            messages.success(request, f'Ticket #{pk} updated!')
            return redirect(get_ticket_panel_route(updated))
    active_page = 'partners' if ticket.is_partner else 'tracking' if ticket.is_new_user else 'tickets'
    return render(request, 'panel/edit_ticket.html', {'form': TicketForm(instance=ticket), 'ticket': ticket, 'active_page': active_page})


@login_required
def panel_delete_ticket(request, pk):
    if request.user.is_superuser:
        ticket = get_scoped_ticket_or_404(request, pk)
        route_name = get_ticket_panel_route(ticket)
        ticket.delete()
        messages.success(request, f'Ticket #{pk} deleted.')
        return redirect(route_name)
    return redirect('panel_dashboard')


@login_required
def panel_ticket_detail(request, pk):
    ticket = get_scoped_ticket_or_404(request, pk)
    remarks = ticket.ticket_remarks.all().order_by('-created_at')
    active_page = 'partners' if ticket.is_partner else 'tracking' if ticket.is_new_user else 'tickets'
    return render(request, 'panel/ticket_detail.html', {'ticket': ticket, 'remarks': remarks, 'status_choices': STATUS_CHOICES, 'active_page': active_page})


@login_required
def panel_update_status(request, pk):
    if request.method == 'POST':
        ticket = get_scoped_ticket_or_404(request, pk)
        new_status = json.loads(request.body).get('status')
        if new_status in dict(STATUS_CHOICES):
            if new_status == 'SOLVED':
                if ticket.is_new_user:
                    if not (ticket.issue or '').strip():
                        return JsonResponse({'success': False, 'error': 'Issue is required before marking this new user ticket as SOLVED.'}, status=400)
                    if not (ticket.user_name or '').strip():
                        return JsonResponse({'success': False, 'error': 'User Name is required before marking this new user ticket as SOLVED.'}, status=400)
                    if not (ticket.customer_id or '').strip():
                        return JsonResponse({'success': False, 'error': 'Customer ID is required before marking this new user ticket as SOLVED.'}, status=400)
                elif not ticket.is_partner and not (ticket.technician_name or '').strip():
                    return JsonResponse({'success': False, 'error': 'Technician must be assigned before marking this ticket as SOLVED.'}, status=400)
            old = ticket.status
            ticket.status = new_status
            ticket.save()
            TicketRemark.objects.create(ticket=ticket, status=new_status, remark=f'Status manually changed from {old} to {new_status}', created_by=request.user.username)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
def panel_add_remark(request, pk):
    ticket = get_scoped_ticket_or_404(request, pk)
    if request.method == 'POST':
        remark_text = request.POST.get('remark', '').strip()
        if remark_text:
            TicketRemark.objects.create(ticket=ticket, status=ticket.status, remark=remark_text, created_by=request.user.username)
            messages.success(request, 'Remark added!')
    return redirect('panel_ticket_detail', pk=pk)


# ─── Reports ────────────────────────────────────────────────────────────────

@login_required
def panel_reports(request):
    today = get_current_date()
    d_from = request.GET.get('date_from', (today - timedelta(days=30)).isoformat())
    d_to = request.GET.get('date_to', today.isoformat())

    tickets = scope_tickets_for_user(Ticket.objects.filter(date__gte=d_from, date__lte=d_to), request.user)
    total = tickets.count()
    solved = tickets.filter(status='SOLVED').count()
    pending = tickets.filter(status='PENDING').count()
    time_taken = tickets.filter(status='TIME TAKEN').count()
    no_response = tickets.filter(status='No Response').count()
    total_new_users = tickets.filter(is_new_user=True, status='SOLVED').count()
    solve_rate = round((solved / total * 100), 1) if total > 0 else 0

    tech_report = list(
        tickets.exclude(technician_name__isnull=True)
        .exclude(technician_name='')
        .values('technician_name')
        .annotate(
            total=Count('sn'),
            solved_count=Count('sn', filter=Q(status='SOLVED')),
            pending_count=Count('sn', filter=Q(status='PENDING')),
        )
        .order_by('-total')
        [:5]
    )

    branch_report = list(
        tickets.values('branch')
        .annotate(
            total=Count('sn'),
            solved_count=Count('sn', filter=Q(status='SOLVED')),
            pending_count=Count('sn', filter=Q(status='PENDING')),
        )
        .order_by('-total')
        [:5]
    )

    for row in branch_report:
        row['branch_raw'] = row.get('branch')
        row['branch'] = format_branch_name(row.get('branch'))

    branch_targets = []
    for b in BranchOption.objects.filter(is_active=True).order_by('sort_order'):
        achieved = tickets.filter(branch=b.name, is_new_user=True, status='SOLVED').count()
        target = b.monthly_target or 0
        progress = min(100, int(achieved / target * 100)) if target > 0 else 0
        branch_targets.append({
            'branch_name': b.display_name, 'target': target, 'achieved': achieved,
            'remaining': max(0, target - achieved), 'progress': progress
        })

    issue_data = list(tickets.values('issue').annotate(total=Count('sn')).order_by('-total')[:10])
    daily_report = list(tickets.values('date').annotate(count=Count('sn')).order_by('date'))
    daily_labels = [d['date'].strftime('%d %b') for d in daily_report]
    daily_values = [d['count'] for d in daily_report]

    ai_agent = ReportingAIAgent()
    ai_report = ai_agent.analyze(
        total=total, solved=solved,
        pending=pending,
        time_taken=time_taken,
        no_response=no_response,
        solve_rate=solve_rate, tech_report=tech_report, branch_report=branch_report,
        issue_report=issue_data, daily_values=daily_values
    )

    context = {
        'active_page': 'reports', 'date_from': d_from, 'date_to': d_to,
        'total': total, 'solved': solved, 'solve_rate': solve_rate,
        'pending': pending, 'time_taken': time_taken, 'no_response': no_response,
        'total_new_users': total_new_users,
        'tech_report': tech_report, 'branch_report': branch_report,
        'branch_targets': branch_targets, 'ai_report': ai_report,
        'issue_report': json.dumps(issue_data),
        'daily_labels': json.dumps(daily_labels),
        'daily_values': json.dumps(daily_values),
    }
    return render(request, 'panel/reports.html', context)


@login_required
def panel_new_user_tracking(request):
    today = get_current_date()
    selected_year = int(request.GET.get('year', today.year))
    selected_branch = request.GET.get('branch', '')

    scoped_branch = get_user_branch_scope(request.user)
    if scoped_branch:
        selected_branch = scoped_branch.name

    valid_new_users = scope_tickets_for_user(Ticket.objects.filter(
        status='SOLVED',
        is_new_user=True,
    ), request.user)

    available_years = list(
        valid_new_users.annotate(year=ExtractYear('date'))
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )
    if not available_years:
        available_years = [today.year]
    if selected_year not in available_years:
        selected_year = available_years[0]

    yearly_qs = valid_new_users.filter(date__year=selected_year)
    if selected_branch:
        yearly_qs = apply_branch_filter(yearly_qs, selected_branch)

    new_user_tickets = scope_tickets_for_user(Ticket.objects.filter(
        is_partner=False,
        is_new_user=True,
        date__year=selected_year,
    ), request.user).order_by('-date', '-time')
    if selected_branch:
        new_user_tickets = apply_branch_filter(new_user_tickets, selected_branch)
    active_new_user_tickets = new_user_tickets.exclude(status='SOLVED')
    solved_new_user_tickets = new_user_tickets.filter(status='SOLVED')

    monthly_rows = list(
        yearly_qs.annotate(month=ExtractMonth('date'))
        .values('month')
        .annotate(total=Count('sn'))
        .order_by('month')
    )
    monthly_counts = {row['month']: row['total'] for row in monthly_rows}
    monthly_labels = [month_abbr[i] for i in range(1, 13)]
    monthly_values = [monthly_counts.get(i, 0) for i in range(1, 13)]

    branch_counts = {
        row['branch']: row['total']
        for row in yearly_qs.values('branch').annotate(total=Count('sn'))
    }
    branch_month_counts = {
        row['branch']: row['total']
        for row in yearly_qs.filter(date__month=today.month).values('branch').annotate(total=Count('sn'))
    }

    branch_performance = []
    active_branches = get_visible_branch_options(request.user)
    for branch in active_branches:
        achieved = branch_counts.get(branch.name, 0) + (
            branch_counts.get(branch.display_name, 0) if branch.display_name != branch.name else 0
        )
        this_month = branch_month_counts.get(branch.name, 0) + (
            branch_month_counts.get(branch.display_name, 0) if branch.display_name != branch.name else 0
        )
        annual_target = (branch.monthly_target or 0) * 12
        progress = round((achieved / annual_target) * 100, 1) if annual_target > 0 else 0
        branch_performance.append({
            'branch_name': branch.display_name,
            'branch_key': branch.name,
            'monthly_target': branch.monthly_target or 0,
            'annual_target': annual_target,
            'achieved': achieved,
            'remaining': max(0, annual_target - achieved) if annual_target > 0 else 0,
            'progress': progress,
            'this_month': this_month,
        })

    branch_performance.sort(key=lambda item: (-item['achieved'], item['branch_name']))
    top_branches = branch_performance[:5]

    total_new_users = yearly_qs.count()
    active_branch_count = sum(1 for item in branch_performance if item['achieved'] > 0)
    monthly_average = round(total_new_users / 12, 1) if total_new_users else 0
    top_branch = top_branches[0] if top_branches else None

    yearly_trend_rows = list(
        valid_new_users.annotate(year=ExtractYear('date'))
        .values('year')
        .annotate(total=Count('sn'))
        .order_by('year')
    )
    yearly_trend_labels = [str(row['year']) for row in yearly_trend_rows]
    yearly_trend_values = [row['total'] for row in yearly_trend_rows]

    branch_chart_labels = [item['branch_name'] for item in top_branches]
    branch_chart_values = [item['achieved'] for item in top_branches]

    context = {
        'active_page': 'tracking',
        'form': TicketForm(initial={'is_new_user': True}),
        'selected_year': selected_year,
        'selected_branch': selected_branch,
        'available_years': available_years,
        'branch_choices': active_branches.values_list('name', 'display_name'),
        'total_new_users': total_new_users,
        'active_branch_count': active_branch_count,
        'monthly_average': monthly_average,
        'top_branch': top_branch,
        'top_branches': top_branches,
        'branch_performance': branch_performance,
        'active_new_user_tickets': active_new_user_tickets[:25],
        'solved_new_user_tickets': solved_new_user_tickets[:25],
        'active_new_user_count': active_new_user_tickets.count(),
        'solved_new_user_count': solved_new_user_tickets.count(),
        'new_user_ticket_count': new_user_tickets.count(),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_values': json.dumps(monthly_values),
        'yearly_trend_labels': json.dumps(yearly_trend_labels),
        'yearly_trend_values': json.dumps(yearly_trend_values),
        'branch_chart_labels': json.dumps(branch_chart_labels),
        'branch_chart_values': json.dumps(branch_chart_values),
        'current_month_label': month_abbr[today.month],
    }
    return render(request, 'panel/new_user_tracking.html', context)


@login_required
def panel_export_csv(request):
    tickets = scope_tickets_for_user(Ticket.objects.all(), request.user).order_by('-date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tickets_{date.today()}.csv"'
    writer = csv.writer(response)
    writer.writerow(['SN', 'Date', 'User', 'Partner User', 'Cust. ID', 'Cell', 'Issue', 'Status', 'Branch', 'Is Partner'])
    for t in tickets:
        writer.writerow([t.sn, t.date, t.user_name, t.partner_user_name, t.customer_id, t.cell_no, t.issue, t.status, t.branch, t.is_partner])
    return response


# ─── User Management ────────────────────────────────────────────────────────

@login_required
def panel_users(request):
    if not request.user.is_superuser:
        return redirect('panel_dashboard')
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'panel/users.html', {'users': users, 'active_page': 'users'})


@login_required
def panel_add_user(request):
    if request.method == 'POST' and request.user.is_superuser:
        password = request.POST.get('password') or ''
        is_superuser = request.POST.get('is_superuser') == 'on'
        is_staff = request.POST.get('is_staff') == 'on' or is_superuser
        try:
            validate_password(password)
            User.objects.create_user(
                username=(request.POST.get('username') or '').strip(),
                password=password,
                first_name=(request.POST.get('first_name') or '').strip(),
                last_name=(request.POST.get('last_name') or '').strip(),
                email=(request.POST.get('email') or '').strip(),
                is_staff=is_staff,
                is_superuser=is_superuser,
                is_active=True,
            )
            messages.success(request, 'User created successfully.')
        except (ValidationError, IntegrityError) as exc:
            messages.error(request, f'Could not create user: {exc}')
    return redirect('panel_users')


@login_required
def panel_edit_user(request, pk):
    if not request.user.is_superuser:
        return redirect('panel_dashboard')
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        new_is_superuser = request.POST.get('is_superuser') == 'on'
        new_is_active = request.POST.get('is_active') == 'on'
        if (is_last_superuser(user) or user.pk == request.user.pk) and (not new_is_superuser or not new_is_active):
            messages.error(request, 'You cannot remove or deactivate the active superadmin account you are using.')
            return redirect('panel_users')

        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.is_superuser = new_is_superuser
        user.is_staff = request.POST.get('is_staff') == 'on' or new_is_superuser
        user.is_active = new_is_active
        try:
            if request.POST.get('password'):
                validate_password(request.POST.get('password'), user)
                user.set_password(request.POST.get('password'))
            user.save()
            messages.success(request, 'User updated.')
        except ValidationError as exc:
            messages.error(request, f'Could not update user: {exc}')
    return redirect('panel_users')


@login_required
def panel_delete_user(request, pk):
    if request.user.is_superuser:
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            messages.error(request, 'You cannot delete your own account.')
        elif is_last_superuser(user):
            messages.error(request, 'You cannot delete the last superadmin account.')
        else:
            user.delete()
            messages.success(request, 'User deleted.')
    return redirect('panel_users')


# ─── Settings & Config ──────────────────────────────────────────────────────

@login_required
def panel_settings(request):
    denied = require_superuser(request)
    if denied:
        return denied

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'change_password':
            current_password = request.POST.get('current_password') or ''
            new_password = request.POST.get('new_password') or ''
            confirm_password = request.POST.get('confirm_password') or ''
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'New password and confirmation do not match.')
            else:
                try:
                    validate_password(new_password, request.user)
                    request.user.set_password(new_password)
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, 'Password changed successfully.')
                except ValidationError as exc:
                    messages.error(request, f'Could not change password: {exc}')
            return redirect('panel_settings')

        if action == 'update_branding':
            brand = PanelBrandSettings.objects.first() or PanelBrandSettings()
            brand.brand_name = (request.POST.get('brand_name') or brand.brand_name).strip()
            brand.brand_subtitle = (request.POST.get('brand_subtitle') or brand.brand_subtitle).strip()
            brand.logo_icon = (request.POST.get('logo_icon') or '').strip()
            brand.logo_url = (request.POST.get('logo_url') or '').strip()
            logo_image = request.FILES.get('logo_image')
            if logo_image:
                is_png = logo_image.name.lower().endswith('.png') and logo_image.content_type == 'image/png'
                if not is_png:
                    messages.error(request, 'Logo upload must be a PNG image.')
                    return redirect('panel_settings')
                brand.logo_image = logo_image
            brand.save()
            messages.success(request, 'Branding updated successfully.')
            return redirect('panel_settings')

    context = {
        'active_page': 'settings',
        'issues': IssueType.objects.all(),
        'technicians': TechnicianOption.objects.all(),
        'branches': BranchOption.objects.all(),
        'partners': PartnerOption.objects.all(),
        'received_by_options': ReceivedByOption.objects.all(),
    }
    return render(request, 'panel/settings.html', context)


@login_required
def config_add(request, config_type):
    denied = require_superuser(request)
    if denied:
        return denied

    models = {
        'issue': IssueType, 'technician': TechnicianOption,
        'branch': BranchOption, 'partner': PartnerOption,
        'received_by': ReceivedByOption
    }
    if request.method == 'POST' and config_type in models:
        try:
            obj = models[config_type](
                name=(request.POST.get('name') or '').strip(),
                display_name=(request.POST.get('display_name') or '').strip(),
                sort_order=int(request.POST.get('sort_order') or 0),
            )
            if config_type == 'branch':
                obj.monthly_target = max(0, int(request.POST.get('monthly_target') or 0))
            obj.save()
            messages.success(request, f'{config_type.capitalize()} added.')
        except (ValueError, IntegrityError) as exc:
            messages.error(request, f'Could not add {config_type}: {exc}')
    return redirect('panel_settings')


@login_required
def config_edit(request, config_type, pk):
    denied = require_superuser(request)
    if denied:
        return denied

    models = {
        'issue': IssueType, 'technician': TechnicianOption,
        'branch': BranchOption, 'partner': PartnerOption,
        'received_by': ReceivedByOption
    }
    if request.method == 'POST' and config_type in models:
        obj = get_object_or_404(models[config_type], pk=pk)
        try:
            obj.name = (request.POST.get('name') or obj.name).strip()
            obj.display_name = (request.POST.get('display_name') or obj.display_name).strip()
            obj.sort_order = int(request.POST.get('sort_order') or 0)
            obj.is_active = request.POST.get('is_active') == 'on'
            if config_type == 'branch':
                obj.monthly_target = max(0, int(request.POST.get('monthly_target') or 0))
            obj.save()
            messages.success(request, f'{config_type.capitalize()} updated.')
        except (ValueError, IntegrityError) as exc:
            messages.error(request, f'Could not update {config_type}: {exc}')
    return redirect('panel_settings')


@login_required
def config_delete(request, config_type, pk):
    denied = require_superuser(request)
    if denied:
        return denied

    models = {
        'issue': IssueType, 'technician': TechnicianOption,
        'branch': BranchOption, 'partner': PartnerOption,
        'received_by': ReceivedByOption
    }
    if request.method == 'POST' and config_type in models:
        models[config_type].objects.filter(pk=pk).delete()
        messages.success(request, f'{config_type.capitalize()} deleted.')
    return redirect('panel_settings')
