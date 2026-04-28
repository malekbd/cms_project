import json
from datetime import date, timedelta, time

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cms_project.middleware import ErrorHandlingMiddleware, SecurityHeadersMiddleware
from tickets.ai_reporting_agent import ReportingAIAgent
from tickets.forms import TicketForm
from tickets.models import (
    BranchOption,
    IssueType,
    PartnerOption,
    ReceivedByOption,
    TechnicianOption,
    Ticket,
    TicketRemark,
)
from tickets.panel_views import (
    apply_branch_filter,
    build_dashboard_payload,
    format_branch_name,
    get_current_date,
    get_ticket_panel_route,
    get_user_branch_scope,
    normalize_key,
)


class BaseTicketTestCase(TestCase):
    def create_options(self):
        self.issue_type = IssueType.objects.create(
            name='internet_issue',
            display_name='Internet Connection Issue',
            is_active=True,
            sort_order=1,
        )
        self.received_by = ReceivedByOption.objects.create(
            name='support_desk',
            display_name='Support Desk',
            is_active=True,
            sort_order=1,
        )
        self.technician = TechnicianOption.objects.create(
            name='tech1',
            display_name='Technician 1',
            is_active=True,
            sort_order=1,
        )
        self.branch = BranchOption.objects.create(
            name='hq',
            display_name='Head Quarter',
            is_active=True,
            sort_order=1,
            monthly_target=10,
        )
        self.partner = PartnerOption.objects.create(
            name='partner_one',
            display_name='Partner One',
            is_active=True,
            sort_order=1,
        )

    def create_ticket(self, **kwargs):
        defaults = {
            'date': date.today(),
            'user_name': 'John Doe',
            'customer_id': 'CUST001',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'branch': 'hq',
            'status': 'PENDING',
        }
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)


class TicketModelTest(BaseTicketTestCase):
    """Test cases for the Ticket model."""

    def setUp(self):
        self.create_options()

    def test_ticket_creation(self):
        ticket = self.create_ticket(user_name='John Doe')
        self.assertEqual(ticket.user_name, 'John Doe')
        self.assertEqual(ticket.status, 'PENDING')
        self.assertIsNotNone(ticket.time)
        self.assertEqual(str(ticket), f"#{ticket.sn} - John Doe (internet_issue)")

    def test_ticket_auto_time_assignment(self):
        ticket = self.create_ticket(user_name='Jane Doe', customer_id='CUST002', cell_no='01812345678')
        self.assertIsNotNone(ticket.time)
        self.assertIsInstance(ticket.time, time)

    def test_ticket_technician_assignment_timestamp(self):
        ticket = self.create_ticket(user_name='Bob Smith', customer_id='CUST003', cell_no='01912345678')
        self.assertIsNone(ticket.technician_assigned_at)
        ticket.technician_name = 'tech1'
        ticket.save()
        self.assertIsNotNone(ticket.technician_assigned_at)
        self.assertIsInstance(ticket.technician_assigned_at, timezone.datetime)

    def test_ticket_solved_timestamp(self):
        ticket = self.create_ticket(user_name='Alice Johnson', customer_id='CUST004', cell_no='01612345678')
        self.assertIsNone(ticket.solved_at)
        ticket.status = 'SOLVED'
        ticket.save()
        self.assertIsNotNone(ticket.solved_at)
        self.assertIsInstance(ticket.solved_at, timezone.datetime)

    def test_ticket_properties(self):
        ticket = self.create_ticket(user_name='Test User', customer_id='CUST005', cell_no='01512345678')
        self.assertFalse(ticket.is_solved)
        ticket.status = 'SOLVED'
        ticket.save()
        self.assertTrue(ticket.is_solved)
        self.assertGreaterEqual(ticket.days_open, 0)
        self.assertFalse(ticket.has_remarks)
        TicketRemark.objects.create(ticket=ticket, status='SOLVED', remark='Test remark', created_by='test_user')
        self.assertTrue(ticket.has_remarks)

    def test_ticket_route_helper(self):
        regular = self.create_ticket()
        partner = self.create_ticket(customer_id='CUSTP01', is_partner=True)
        new_user = self.create_ticket(customer_id='CUSTN01', is_new_user=True)
        self.assertEqual(get_ticket_panel_route(regular), 'panel_tickets')
        self.assertEqual(get_ticket_panel_route(partner), 'panel_partner_tickets')
        self.assertEqual(get_ticket_panel_route(new_user), 'panel_new_user_tracking')


class TicketFormTest(BaseTicketTestCase):
    """Test cases for the TicketForm."""

    def setUp(self):
        self.create_options()

    def base_form_data(self, **kwargs):
        data = {
            'date': date.today(),
            'user_name': 'John Doe',
            'customer_id': 'CUST001',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'technician_name': 'tech1',
            'status': 'PENDING',
            'branch': 'hq',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        data.update(kwargs)
        return data

    def test_form_valid_data(self):
        form = TicketForm(data=self.base_form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalid_phone_number(self):
        form = TicketForm(data=self.base_form_data(cell_no='12345'))
        self.assertFalse(form.is_valid())
        self.assertIn('cell_no', form.errors)

    def test_form_invalid_customer_id(self):
        form = TicketForm(data=self.base_form_data(customer_id='cust001'))
        self.assertFalse(form.is_valid())
        self.assertIn('customer_id', form.errors)

    def test_form_future_date_validation(self):
        form = TicketForm(data=self.base_form_data(date=date.today() + timedelta(days=1)))
        self.assertFalse(form.is_valid())
        self.assertIn('date', form.errors)

    def test_form_solved_without_technician(self):
        form = TicketForm(data=self.base_form_data(status='SOLVED', technician_name=''))
        self.assertFalse(form.is_valid())
        self.assertIn('technician_name', form.errors)

    def test_user_name_and_customer_id_required_when_new_user_ticket_is_solved(self):
        form = TicketForm(data=self.base_form_data(
            user_name='',
            customer_id='',
            status='SOLVED',
            is_new_user='on',
            new_user_id='',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('user_name', form.errors)
        self.assertIn('customer_id', form.errors)

    def test_new_user_id_not_required_for_solved_new_user_ticket(self):
        form = TicketForm(data=self.base_form_data(
            user_name='New Customer',
            customer_id='CUST010',
            issue='NEW USER',
            status='SOLVED',
            is_new_user='on',
            new_user_id='',
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_new_user_id_not_required_until_solved(self):
        form = TicketForm(data=self.base_form_data(
            user_name='New Customer',
            customer_id='CUST011',
            issue='NEW USER',
            technician_name='',
            status='PENDING',
            is_new_user='on',
            new_user_id='',
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_new_user_issue_is_required(self):
        form = TicketForm(data=self.base_form_data(
            user_name='New Customer',
            customer_id='CUST012',
            issue='',
            technician_name='',
            status='PENDING',
            is_new_user='on',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('issue', form.errors)

    def test_partner_form_requires_partner_and_user_name(self):
        form = TicketForm(data=self.base_form_data(
            user_name='partner_one',
            partner_user_name='',
            customer_id='',
            branch='',
            is_partner='True',
        ), initial={'is_partner': True})
        self.assertFalse(form.is_valid())
        self.assertIn('partner_user_name', form.errors)

    def test_partner_form_accepts_separate_user_name(self):
        form = TicketForm(data=self.base_form_data(
            user_name='partner_one',
            partner_user_name='Ariful Islam',
            customer_id='',
            branch='',
            is_partner='True',
        ), initial={'is_partner': True})
        self.assertTrue(form.is_valid(), form.errors)


class TicketViewTest(BaseTicketTestCase):
    """Test cases for ticket views."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.superuser = User.objects.create_superuser(username='admin', password='adminpass123')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        self.create_options()

    def test_login_required_redirects_anonymous_user(self):
        self.client.logout()
        response = self.client.get('/panel/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/login/', response.url)

    def test_login_page_invalid_credentials(self):
        self.client.logout()
        response = self.client.post('/panel/login/', {'username': 'bad', 'password': 'bad'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_login_page_redirects_authenticated_user(self):
        response = self.client.get('/panel/login/')
        self.assertEqual(response.status_code, 302)

    def test_logout_view(self):
        response = self.client.get('/panel/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/login/', response.url)

    def test_dashboard_view(self):
        response = self.client.get('/panel/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_dashboard_data_view(self):
        self.create_ticket(user_name='Live Dashboard User', customer_id='LIVE001')
        response = self.client.get('/panel/dashboard/data/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['pending'], 1)
        self.assertIn('recent_tickets', data)
        self.assertEqual(data['recent_tickets'][0]['user_name'], 'Live Dashboard User')

    def test_tickets_list_view(self):
        response = self.client.get('/panel/tickets/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tickets')

    def test_tickets_list_filters(self):
        self.create_ticket(user_name='Alpha User', customer_id='CUST100', technician_name='tech1')
        self.create_ticket(user_name='Beta User', customer_id='CUST101', issue='internet_issue', status='SOLVED', technician_name='tech1')
        response = self.client.get('/panel/tickets/', {
            'search': 'Alpha',
            'status': 'PENDING',
            'branch': 'hq',
            'issue': 'internet_issue',
            'technician': 'tech1',
            'date_from': date.today().isoformat(),
            'date_to': date.today().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha User')
        self.assertNotContains(response, 'Beta User')

    def test_add_ticket_post_creates_ticket_and_remark(self):
        response = self.client.post('/panel/tickets/add/', {
            'date': date.today().isoformat(),
            'user_name': 'Created User',
            'customer_id': 'CUST200',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'technician_name': '',
            'status': 'PENDING',
            'branch': 'hq',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': 'Created from test',
        })
        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get(customer_id='CUST200')
        self.assertEqual(ticket.user_name, 'Created User')
        self.assertTrue(ticket.ticket_remarks.filter(remark='Created from test').exists())

    def test_add_partner_ticket_redirects_partner_page(self):
        response = self.client.post('/panel/tickets/add/', {
            'date': date.today().isoformat(),
            'user_name': 'partner_one',
            'partner_user_name': 'Partner Client',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'is_partner': 'True',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/partners/', response.url)

    def test_add_new_user_ticket_redirects_new_user_page(self):
        response = self.client.post('/panel/tickets/add/', {
            'date': date.today().isoformat(),
            'user_name': 'New Client',
            'customer_id': 'CUST201',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'branch': 'hq',
            'is_new_user': 'on',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/new-users/', response.url)

    def test_general_ticket_list_excludes_new_user_tickets(self):
        self.create_ticket(user_name='Regular User', customer_id='CUST300')
        self.create_ticket(user_name='New User Queue', customer_id='CUST301', is_new_user=True)
        response = self.client.get('/panel/tickets/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Regular User')
        self.assertNotContains(response, 'New User Queue')

    def test_partner_tickets_view_search_and_status(self):
        self.create_ticket(user_name='partner_one', partner_user_name='Partner Customer', customer_id='', is_partner=True)
        response = self.client.get('/panel/partners/', {'search': 'Partner Customer', 'status': 'PENDING'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partner Customer')

    def test_edit_ticket_get_and_post(self):
        ticket = self.create_ticket(customer_id='CUST400')
        response = self.client.get(f'/panel/tickets/edit/{ticket.sn}/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/panel/tickets/edit/{ticket.sn}/', {
            'date': ticket.date.isoformat(),
            'user_name': 'Updated User',
            'customer_id': 'CUST400',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'branch': 'hq',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': 'Updated remark',
        })
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.user_name, 'Updated User')
        self.assertTrue(ticket.ticket_remarks.filter(remark='Updated remark').exists())

    def test_edit_new_user_ticket_redirects_to_new_user_module(self):
        ticket = self.create_ticket(customer_id='CUST401', is_new_user=True, user_name='Module User')
        response = self.client.post(f'/panel/tickets/edit/{ticket.sn}/', {
            'date': ticket.date.isoformat(),
            'user_name': 'Module User',
            'customer_id': 'CUST401',
            'cell_no': '01733333333',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'branch': 'hq',
            'is_new_user': 'on',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/new-users/', response.url)

    def test_ticket_detail_and_add_remark(self):
        ticket = self.create_ticket(customer_id='CUST500')
        response = self.client.get(reverse('panel_ticket_detail', args=[ticket.sn]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('panel_add_remark', args=[ticket.sn]), {'remark': 'Follow up needed'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ticket.ticket_remarks.filter(remark='Follow up needed').exists())

    def test_delete_ticket_requires_superuser(self):
        ticket = self.create_ticket(customer_id='CUST600')
        response = self.client.post(f'/panel/tickets/delete/{ticket.sn}/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Ticket.objects.filter(sn=ticket.sn).exists())

    def test_delete_ticket_superuser(self):
        self.client.logout()
        self.client.login(username='admin', password='adminpass123')
        ticket = self.create_ticket(customer_id='CUST601')
        response = self.client.post(f'/panel/tickets/delete/{ticket.sn}/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Ticket.objects.filter(sn=ticket.sn).exists())

    def test_quick_status_update_success(self):
        ticket = self.create_ticket(customer_id='CUST700', technician_name='tech1')
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'SOLVED')
        self.assertTrue(ticket.ticket_remarks.exists())

    def test_quick_status_update_blocks_regular_solve_without_technician(self):
        ticket = self.create_ticket(customer_id='CUST701', technician_name='')
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Technician', response.json()['error'])

    def test_quick_status_update_blocks_invalid_new_user_solve(self):
        ticket = self.create_ticket(user_name='', customer_id='', cell_no='01744444444', is_new_user=True)
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json()['error'])

    def test_quick_status_update_blocks_new_user_solve_without_issue(self):
        ticket = self.create_ticket(
            user_name='New User',
            customer_id='CUST702',
            issue='',
            is_new_user=True,
            technician_name='tech1',
        )
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Issue is required', response.json()['error'])

    def test_quick_status_update_invalid_payload(self):
        ticket = self.create_ticket(customer_id='CUST703')
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'INVALID'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_export_csv(self):
        self.create_ticket(customer_id='CUST800')
        response = self.client.get('/panel/reports/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('tickets_', response['Content-Disposition'])
        self.assertContains(response, 'CUST800')


class TicketNewUserReportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reportuser', password='testpass123')
        self.client = Client()
        self.client.login(username='reportuser', password='testpass123')
        self.issue_type = IssueType.objects.create(name='connection', display_name='Connection', is_active=True)
        self.received_by = ReceivedByOption.objects.create(name='desk', display_name='Desk', is_active=True)
        self.branch = BranchOption.objects.create(name='north_hub', display_name='North Hub', is_active=True, monthly_target=10)

        Ticket.objects.create(
            date=date.today(),
            user_name='Solved New User',
            customer_id='NU001',
            cell_no='01712345678',
            issue='connection',
            received_by='desk',
            technician_name='tech1',
            status='SOLVED',
            branch='north_hub',
            is_new_user=True,
            new_user_id='NU-001',
        )
        Ticket.objects.create(
            date=date.today(),
            user_name='Pending New User',
            customer_id='NU002',
            cell_no='01712345679',
            issue='connection',
            received_by='desk',
            status='PENDING',
            branch='north_hub',
            is_new_user=True,
        )
        Ticket.objects.create(
            date=date.today().replace(year=date.today().year - 1),
            user_name='Last Year User',
            customer_id='NU003',
            cell_no='01712345670',
            issue='connection',
            received_by='desk',
            technician_name='tech1',
            status='SOLVED',
            branch='north_hub',
            is_new_user=True,
            new_user_id='NU-OLD',
        )

    def test_reports_count_only_solved_new_user_tickets(self):
        response = self.client.get('/panel/reports/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total New Users')
        self.assertContains(response, 'North Hub')
        self.assertEqual(response.context['total_new_users'], 1)

    def test_reports_with_explicit_date_range(self):
        response = self.client.get('/panel/reports/', {
            'date_from': date.today().isoformat(),
            'date_to': date.today().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], 2)
        self.assertIn('ai_report', response.context)

    def test_new_user_tracking_page_uses_selected_year(self):
        response = self.client.get('/panel/new-users/', {'year': date.today().year})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New User Tracking')
        self.assertEqual(response.context['total_new_users'], 1)
        self.assertEqual(response.context['top_branch']['branch_name'], 'North Hub')
        self.assertEqual(response.context['new_user_ticket_count'], 2)
        self.assertContains(response, 'Pending New User')
        self.assertEqual(response.context['active_new_user_count'], 1)
        self.assertEqual(response.context['solved_new_user_count'], 1)

    def test_new_user_tracking_counts_solved_ticket_without_new_user_id(self):
        Ticket.objects.create(
            date=date.today(),
            user_name='Solved Without ID',
            customer_id='NU004',
            cell_no='01712345671',
            issue='NEW USER',
            received_by='desk',
            technician_name='tech1',
            status='SOLVED',
            branch='north_hub',
            is_new_user=True,
            new_user_id='',
        )
        response = self.client.get('/panel/new-users/', {'year': date.today().year})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_new_users'], 2)
        self.assertEqual(response.context['solved_new_user_count'], 2)

    def test_new_user_tracking_branch_filter(self):
        response = self.client.get('/panel/new-users/', {'year': date.today().year, 'branch': 'north_hub'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_branch'], 'north_hub')
        self.assertEqual(response.context['total_new_users'], 1)


class PanelSettingsAndUserViewTest(BaseTicketTestCase):
    def setUp(self):
        self.create_options()
        self.user = User.objects.create_user(username='normal', password='normalpass123')
        self.superuser = User.objects.create_superuser(username='super', password='superpass123', email='super@example.com')
        self.client = Client()

    def test_settings_requires_superuser(self):
        self.client.login(username='normal', password='normalpass123')
        response = self.client.get('/panel/settings/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/panel/', response.url)

    def test_settings_superuser_can_view(self):
        self.client.login(username='super', password='superpass123')
        response = self.client.get('/panel/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Settings')

    def test_config_add_edit_delete_issue(self):
        self.client.login(username='super', password='superpass123')
        response = self.client.post(reverse('config_add', args=['issue']), {
            'name': 'billing',
            'display_name': 'Billing',
            'sort_order': '2',
        })
        self.assertEqual(response.status_code, 302)
        issue = IssueType.objects.get(name='billing')

        response = self.client.post(reverse('config_edit', args=['issue', issue.pk]), {
            'name': 'billing_updated',
            'display_name': 'Billing Updated',
            'sort_order': '3',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        issue.refresh_from_db()
        self.assertEqual(issue.name, 'billing_updated')

        response = self.client.post(reverse('config_delete', args=['issue', issue.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(IssueType.objects.filter(pk=issue.pk).exists())

    def test_config_add_branch_sets_monthly_target(self):
        self.client.login(username='super', password='superpass123')
        response = self.client.post(reverse('config_add', args=['branch']), {
            'name': 'east_hub',
            'display_name': 'East Hub',
            'sort_order': '2',
            'monthly_target': '15',
        })
        self.assertEqual(response.status_code, 302)
        branch = BranchOption.objects.get(name='east_hub')
        self.assertEqual(branch.monthly_target, 15)

    def test_users_view_requires_superuser(self):
        self.client.login(username='normal', password='normalpass123')
        response = self.client.get('/panel/users/')
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_create_edit_delete_user(self):
        self.client.login(username='super', password='superpass123')
        response = self.client.post('/panel/users/add/', {
            'username': 'newstaff',
            'password': 'StrongPass123!abc',
            'first_name': 'New',
            'last_name': 'Staff',
            'email': 'newstaff@example.com',
            'is_staff': 'on',
        })
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='newstaff')

        response = self.client.post(reverse('panel_edit_user', args=[created.pk]), {
            'first_name': 'Updated',
            'last_name': 'Staff',
            'email': 'updated@example.com',
            'is_active': 'on',
            'is_staff': 'on',
        })
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.first_name, 'Updated')

        response = self.client.post(reverse('panel_delete_user', args=[created.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=created.pk).exists())

    def test_cannot_delete_self_superuser(self):
        self.client.login(username='super', password='superpass123')
        response = self.client.post(reverse('panel_delete_user', args=[self.superuser.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())


class BranchScopeHelperTest(BaseTicketTestCase):
    def setUp(self):
        self.create_options()
        self.branch.display_name = 'Head Quarter Branch'
        self.branch.save()
        self.normal_user = User.objects.create_user(username='normal', password='pass')
        self.branch_user = User.objects.create_user(username='frc-hq', password='pass')
        self.superuser = User.objects.create_superuser(username='rootuser', password='pass')

    def test_normalize_key(self):
        self.assertEqual(normalize_key('Head Quarter Branch'), 'headquarterbranch')
        self.assertEqual(normalize_key('FRC-HQ'), 'frchq')

    def test_get_user_branch_scope(self):
        self.assertIsNone(get_user_branch_scope(self.normal_user))
        self.assertIsNone(get_user_branch_scope(self.superuser))
        self.assertEqual(get_user_branch_scope(self.branch_user), self.branch)

    def test_apply_branch_filter_matches_name_or_display_name(self):
        ticket = self.create_ticket(branch='hq')
        self.create_ticket(customer_id='OTHER01', branch='Other')
        filtered = apply_branch_filter(Ticket.objects.all(), 'Head Quarter Branch')
        self.assertEqual(list(filtered), [ticket])

    def test_format_branch_name(self):
        self.assertEqual(format_branch_name('hq'), 'Head Quarter Branch')
        self.assertEqual(format_branch_name('north_hub'), 'North Hub')
        self.assertEqual(format_branch_name(''), 'No Branch')

    def test_build_dashboard_payload_scopes_branch_user(self):
        self.create_ticket(branch='hq', customer_id='BR001')
        self.create_ticket(branch='Other', customer_id='BR002')
        payload = build_dashboard_payload(self.branch_user)
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['recent_tickets'][0]['user_name'], 'John Doe')


class MiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_security_headers_middleware_adds_headers(self):
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = self.factory.get('/')
        response = SecurityHeadersMiddleware(get_response)(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Content-Type-Options', response.headers)
        self.assertIn('Referrer-Policy', response.headers)

    def test_error_handling_middleware_passes_successful_response(self):
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = self.factory.get('/')
        response = ErrorHandlingMiddleware(get_response)(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    @override_settings(DEBUG=False)
    def test_error_handling_middleware_handles_exception(self):
        def get_response(request):
            raise RuntimeError('boom')

        request = self.factory.get('/')
        with self.assertRaises(RuntimeError):
            ErrorHandlingMiddleware(get_response)(request)


class ReportingAIAgentTest(TestCase):
    def test_ai_agent_empty_report(self):
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=0,
            solved=0,
            pending=0,
            time_taken=0,
            no_response=0,
            solve_rate=0,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[],
        )
        self.assertIsInstance(result, dict)
        self.assertIn('headline', result)
        self.assertIn('health', result)

    def test_ai_agent_critical_report(self):
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=2,
            pending=7,
            time_taken=1,
            no_response=0,
            solve_rate=20,
            tech_report=[{'technician_name': 'tech1', 'total': 5, 'solved_count': 3}],
            branch_report=[{'branch': 'North Hub', 'total': 6, 'solved_count': 2}],
            issue_report=[{'issue': 'connection', 'total': 6}],
            daily_values=[1, 2, 3, 4],
        )
        self.assertIsInstance(result, dict)
        self.assertIn(result['health'], ['critical', 'warning', 'good'])
        self.assertTrue(result['insights'])
        self.assertTrue(result.get('actions') or result.get('recommendations') or result.get('insights'))

    def test_ai_agent_good_report(self):
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=9,
            pending=1,
            time_taken=0,
            no_response=0,
            solve_rate=90,
            tech_report=[{'technician_name': 'tech1', 'total': 5, 'solved_count': 5}],
            branch_report=[{'branch': 'Head Quarter', 'total': 5, 'solved_count': 5}],
            issue_report=[{'issue': 'connection', 'total': 3}],
            daily_values=[1, 1, 1],
        )
        self.assertIsInstance(result, dict)
        self.assertIn('health', result)


class URLSmokeTest(TestCase):
    def test_named_urls_resolve_for_known_routes(self):
        # Keeps cms_project/urls.py and panel_urls.py imported through URL reversing.
        self.assertTrue(reverse('panel_login').endswith('/panel/login/'))
        self.assertTrue(reverse('panel_dashboard').endswith('/panel/'))
        self.assertTrue(reverse('panel_tickets').endswith('/panel/tickets/'))
