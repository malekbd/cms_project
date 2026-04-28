from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone
import json
from datetime import date

from .models import Ticket, STATUS_CHOICES
from .forms import TicketForm


@login_required
def dashboard(request):
    today = date.today()
    tickets = Ticket.objects.all()

    # Filters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        tickets = tickets.filter(
            Q(user_name__icontains=search) |
            Q(customer_id__icontains=search) |
            Q(cell_no__icontains=search) |
            Q(issue__icontains=search)
        )
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if branch_filter:
        tickets = tickets.filter(branch=branch_filter)
    if date_from:
        tickets = tickets.filter(date__gte=date_from)
    if date_to:
        tickets = tickets.filter(date__lte=date_to)

    # Stats
    total = Ticket.objects.count()
    solved = Ticket.objects.filter(status='SOLVED').count()
    pending = Ticket.objects.filter(status='PENDING').count()
    time_taken = Ticket.objects.filter(status='TIME TAKEN').count()
    no_response = Ticket.objects.filter(status='No Response').count()
    today_count = Ticket.objects.filter(date=today).count()

    # Issue stats for chart
    issue_stats = Ticket.objects.values('issue').annotate(count=Count('issue')).order_by('-count')[:8]

    context = {
        'tickets': tickets,
        'form': TicketForm(),
        'total': total,
        'solved': solved,
        'pending': pending,
        'time_taken': time_taken,
        'no_response': no_response,
        'today_count': today_count,
        'issue_stats': json.dumps(list(issue_stats)),
        'search': search,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
        'date_from': date_from,
        'date_to': date_to,
        'branches': [],
    }
    return render(request, 'tickets/dashboard.html', context)


@login_required
def add_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save()
            messages.success(request, f'Ticket #{ticket.sn} added successfully!')
        else:
            messages.error(request, 'Error adding ticket. Please check the form.')
    return redirect('dashboard')


@login_required
def edit_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, f'Ticket #{pk} updated successfully!')
            return redirect('dashboard')
    else:
        form = TicketForm(instance=ticket)
    return render(request, 'tickets/edit_ticket.html', {'form': form, 'ticket': ticket})


@login_required
def delete_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, f'Ticket #{pk} deleted.')
    return redirect('dashboard')


@login_required
def update_status(request, pk):
    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, pk=pk)
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status in dict(STATUS_CHOICES):
            ticket.status = new_status
            ticket.save()
            return JsonResponse({'success': True, 'status': new_status})
    return JsonResponse({'success': False}, status=400)


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    return render(request, 'tickets/ticket_detail.html', {'ticket': ticket})
