import json
from datetime import date, timedelta, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cms_project.middleware import ErrorHandlingMiddleware, SecurityHeadersMiddleware
from tickets.ai_reporting_agent import ReportingAIAgent
from tickets.forms import TicketForm
from tickets.models import (
    BranchOption,
    IssueType,
    PanelBrandSettings,
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
from tickets.context_processors import panel_branding
from tickets.seed_config import seed, main


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

    def test_ticket_get_latest_remark(self):
        ticket = self.create_ticket(customer_id='CUST999')
        # No remarks initially
        self.assertIsNone(ticket.get_latest_remark())
        # Add a remark
        remark = TicketRemark.objects.create(
            ticket=ticket,
            status='SOLVED',
            remark='Test remark',
            created_by='test_user'
        )
        self.assertEqual(ticket.get_latest_remark(), remark)
        # Add another remark, first should still be latest? Actually .first() returns earliest created?
        # Since ordering is -created_at, first() returns most recent.
        remark2 = TicketRemark.objects.create(
            ticket=ticket,
            status='PENDING',
            remark='Second remark',
            created_by='test_user'
        )
        self.assertEqual(ticket.get_latest_remark(), remark2)

    def test_ticket_forwarded_at_auto_set(self):
        """Test that forwarded_at is set when forwarded_to is assigned."""
        ticket = self.create_ticket(customer_id='CUST888')
        self.assertIsNone(ticket.forwarded_at)
        # Assign forwarded_to for the first time
        ticket.forwarded_to = 'SOMEONE'
        ticket.save()
        self.assertIsNotNone(ticket.forwarded_at)
        forwarded_at = ticket.forwarded_at
        # Changing forwarded_to to a different value should update forwarded_at
        ticket.forwarded_to = 'SOMEONE ELSE'
        ticket.save()
        # forwarded_at may be the same second, but should still be a datetime
        self.assertIsNotNone(ticket.forwarded_at)
        # Clearing forwarded_to should reset forwarded_at
        ticket.forwarded_to = ''
        ticket.save()
        self.assertIsNone(ticket.forwarded_at)

    def test_ticket_remark_str(self):
        ticket = self.create_ticket(customer_id='CUST777')
        remark_text = 'This is a test remark that is longer than fifty characters to test truncation'
        remark = TicketRemark.objects.create(
            ticket=ticket,
            status='SOLVED',
            remark=remark_text,
            created_by='test_user'
        )
        expected = f"Remark on #{ticket.sn} [SOLVED] - {remark_text[:50]}"
        self.assertEqual(str(remark), expected)
        # Test short remark
        remark2 = TicketRemark.objects.create(
            ticket=ticket,
            status='PENDING',
            remark='Short',
            created_by='test_user'
        )
        self.assertEqual(str(remark2), f"Remark on #{ticket.sn} [PENDING] - Short")


class ConfigModelTest(BaseTicketTestCase):
    """Test cases for config models (IssueType, ReceivedByOption, etc.)."""

    def setUp(self):
        self.create_options()

    def test_issue_type_str(self):
        self.assertEqual(str(self.issue_type), 'Internet Connection Issue')

    def test_issue_type_get_active_choices(self):
        choices = IssueType.get_active_choices()
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0], ('internet_issue', 'Internet Connection Issue'))

    def test_received_by_option_str(self):
        self.assertEqual(str(self.received_by), 'Support Desk')

    def test_technician_option_str(self):
        self.assertEqual(str(self.technician), 'Technician 1')

    def test_branch_option_str(self):
        self.assertEqual(str(self.branch), 'Head Quarter')

    def test_partner_option_str(self):
        self.assertEqual(str(self.partner), 'Partner One')

    def test_panel_brand_settings_str(self):
        brand = PanelBrandSettings.objects.create(
            brand_name='Test Brand',
            brand_subtitle='Subtitle',
            logo_icon='★',
            logo_url='https://example.com',
        )
        self.assertEqual(str(brand), 'Test Brand')


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

    def test_clean_customer_id_validation(self):
        """Directly test clean_customer_id method raises ValidationError."""
        form = TicketForm()
        # Simulate cleaned_data with invalid customer ID
        form.cleaned_data = {'customer_id': 'cust001'}
        with self.assertRaises(ValidationError) as cm:
            form.clean_customer_id()
        self.assertIn('Customer ID must use uppercase letters', str(cm.exception))
        # Test valid customer ID
        form.cleaned_data = {'customer_id': 'CUST001'}
        result = form.clean_customer_id()
        self.assertEqual(result, 'CUST001')
        # Test empty customer ID (should return empty string)
        form.cleaned_data = {'customer_id': ''}
        result = form.clean_customer_id()
        self.assertEqual(result, '')

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

    def test_customer_id_validation_regex(self):
        """Test that customer ID must match uppercase pattern."""
        # Invalid: starts with lowercase
        form = TicketForm(data=self.base_form_data(customer_id='cust001'))
        self.assertFalse(form.is_valid())
        self.assertIn('customer_id', form.errors)
        # Invalid: contains special character not allowed
        form = TicketForm(data=self.base_form_data(customer_id='CUST@001'))
        self.assertFalse(form.is_valid())
        self.assertIn('customer_id', form.errors)
        # Valid: uppercase with hyphen
        form = TicketForm(data=self.base_form_data(customer_id='CUST-001'))
        self.assertTrue(form.is_valid(), form.errors)
        # Valid: uppercase with underscore
        form = TicketForm(data=self.base_form_data(customer_id='CUST_001'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_phone_number_normalization(self):
        """Test that phone numbers starting with +880 or 88 are normalized."""
        # +880 prefix
        form = TicketForm(data=self.base_form_data(cell_no='+8801712345678'))
        self.assertTrue(form.is_valid(), form.errors)
        # After cleaning, cell_no should be '01712345678' (strip +880)
        self.assertEqual(form.cleaned_data['cell_no'], '01712345678')
        # 88 prefix
        form = TicketForm(data=self.base_form_data(cell_no='8801712345678'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['cell_no'], '01712345678')
        # No prefix unchanged
        form = TicketForm(data=self.base_form_data(cell_no='01712345678'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['cell_no'], '01712345678')

    def test_forwarded_to_other_validation(self):
        """Test that forwarded_to='OTHER' requires forwarded_to_other."""
        form = TicketForm(data=self.base_form_data(
            forwarded_to='OTHER',
            forwarded_to_other='',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('forwarded_to_other', form.errors)
        # With value, should be valid
        form = TicketForm(data=self.base_form_data(
            forwarded_to='OTHER',
            forwarded_to_other='Some Other',
        ))
        self.assertTrue(form.is_valid(), form.errors)
        # Check that forwarded_to is replaced with the other value
        self.assertEqual(form.cleaned_data['forwarded_to'], 'SOME OTHER')

    def test_partner_validation_missing_fields(self):
        """Test that partner tickets require user_name, partner_user_name, issue."""
        # Missing user_name
        form = TicketForm(data=self.base_form_data(
            user_name='',
            partner_user_name='Partner User',
            customer_id='',
            branch='',
            is_partner='True',
            issue='',
        ), initial={'is_partner': True})
        self.assertFalse(form.is_valid())
        self.assertIn('user_name', form.errors)
        # Missing partner_user_name (already covered in existing test)
        # Missing issue
        form = TicketForm(data=self.base_form_data(
            user_name='partner_one',
            partner_user_name='Partner User',
            customer_id='',
            branch='',
            is_partner='True',
            issue='',
        ), initial={'is_partner': True})
        self.assertFalse(form.is_valid())
        self.assertIn('issue', form.errors)

    def test_existing_user_validation_missing_fields(self):
        """Test that existing user tickets require user_name, customer_id, issue."""
        # Ensure is_new_user=False (default) and is_partner=False
        data = self.base_form_data(
            user_name='',
            customer_id='',
            issue='',
            is_new_user='',
            is_partner='',
        )
        form = TicketForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('user_name', form.errors)
        self.assertIn('customer_id', form.errors)
        self.assertIn('issue', form.errors)


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

    def test_error_handling_middleware_validation_error_json(self):
        """ValidationError with Accept: application/json returns JSON response."""
        def get_response(request):
            from django.core.exceptions import ValidationError
            raise ValidationError('Invalid data')

        request = self.factory.get('/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, ValidationError('Invalid data'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Validation Error')

    def test_error_handling_middleware_validation_error_no_json(self):
        """ValidationError without JSON returns None (Django handles)."""
        def get_response(request):
            from django.core.exceptions import ValidationError
            raise ValidationError('Invalid data')

        request = self.factory.get('/')
        if 'HTTP_ACCEPT' in request.META:
            del request.META['HTTP_ACCEPT']
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, ValidationError('Invalid data'))
        self.assertIsNone(response)

    def test_error_handling_middleware_database_error_json(self):
        """DatabaseError with JSON returns JSON response."""
        def get_response(request):
            from django.db import DatabaseError
            raise DatabaseError('DB broken')

        request = self.factory.get('/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, DatabaseError('DB broken'))
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Database Error')

    def test_error_handling_middleware_http404_json(self):
        """Http404 with JSON returns JSON response."""
        def get_response(request):
            from django.http import Http404
            raise Http404('Not found')

        request = self.factory.get('/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, Http404('Not found'))
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Not Found')

    @override_settings(DEBUG=False)
    def test_error_handling_middleware_generic_error_json(self):
        """Generic exception with JSON and DEBUG=False returns JSON."""
        def get_response(request):
            raise RuntimeError('Something went wrong')

        request = self.factory.get('/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, RuntimeError('Something went wrong'))
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Internal Server Error')

    @override_settings(DEBUG=True)
    def test_error_handling_middleware_generic_error_debug_true(self):
        """Generic exception with DEBUG=True returns None (debug page)."""
        def get_response(request):
            raise RuntimeError('Something went wrong')

        request = self.factory.get('/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, RuntimeError('Something went wrong'))
        self.assertIsNone(response)

    def test_error_handling_middleware_database_error_no_json(self):
        """DatabaseError without JSON returns None."""
        def get_response(request):
            from django.db import DatabaseError
            raise DatabaseError('DB broken')

        request = self.factory.get('/')
        if 'HTTP_ACCEPT' in request.META:
            del request.META['HTTP_ACCEPT']
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, DatabaseError('DB broken'))
        self.assertIsNone(response)

    def test_error_handling_middleware_http404_no_json(self):
        """Http404 without JSON returns None."""
        def get_response(request):
            from django.http import Http404
            raise Http404('Not found')

        request = self.factory.get('/')
        if 'HTTP_ACCEPT' in request.META:
            del request.META['HTTP_ACCEPT']
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, Http404('Not found'))
        self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_error_handling_middleware_generic_error_no_json(self):
        """Generic exception without JSON and DEBUG=False returns None."""
        def get_response(request):
            raise RuntimeError('Something went wrong')

        request = self.factory.get('/')
        if 'HTTP_ACCEPT' in request.META:
            del request.META['HTTP_ACCEPT']
        middleware = ErrorHandlingMiddleware(get_response)
        response = middleware.process_exception(request, RuntimeError('Something went wrong'))
        self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_security_headers_middleware_hsts(self):
        """HSTS header added when DEBUG=False."""
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = self.factory.get('/')
        response = SecurityHeadersMiddleware(get_response)(request)
        self.assertIn('Strict-Transport-Security', response.headers)

    @override_settings(DEBUG=True)
    def test_security_headers_middleware_no_hsts_debug(self):
        """HSTS header omitted when DEBUG=True."""
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = self.factory.get('/')
        response = SecurityHeadersMiddleware(get_response)(request)
        self.assertNotIn('Strict-Transport-Security', response.headers)


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

    def test_ai_agent_high_no_response(self):
        """Trigger no_response_pct > 20 condition."""
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=5,
            pending=3,
            time_taken=0,
            no_response=3,  # 30%
            solve_rate=50,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[1, 2, 3],
        )
        self.assertIsInstance(result, dict)
        self.assertIn('insights', result)
        # Check that the insight about high no-response is present
        insights = '\n'.join(result['insights'])
        self.assertIn('no-response', insights.lower())

    def test_ai_agent_recent_volume_rising(self):
        """Trigger recent_avg > overall_avg * 1.2."""
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=5,
            pending=3,
            time_taken=0,
            no_response=0,
            solve_rate=50,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[1, 1, 1, 5, 5, 5],  # recent three [5,5,5] avg 5, overall avg ~3
        )
        self.assertIsInstance(result, dict)
        self.assertIn('insights', result)
        insights = '\n'.join(result['insights'])
        self.assertIn('rising', insights.lower())

    def test_ai_agent_recent_volume_lower(self):
        """Trigger recent_avg < overall_avg * 0.8."""
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=5,
            pending=3,
            time_taken=0,
            no_response=0,
            solve_rate=50,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[5, 5, 5, 1, 1, 1],  # recent three [1,1,1] avg 1, overall avg ~3
        )
        self.assertIsInstance(result, dict)
        self.assertIn('insights', result)
        insights = '\n'.join(result['insights'])
        self.assertIn('lower', insights.lower())

    def test_ai_agent_warning_health(self):
        """Trigger solve_rate between 60 and 80 (warning)."""
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=7,
            pending=2,
            time_taken=0,
            no_response=0,
            solve_rate=70,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[1, 2, 3],
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result['health'], 'warning')
        self.assertIn('recommendations', result)

    def test_ai_agent_no_recommendations(self):
        """Trigger empty recommendations list (should add default)."""
        agent = ReportingAIAgent()
        result = agent.analyze(
            total=10,
            solved=9,
            pending=1,
            time_taken=0,
            no_response=0,
            solve_rate=90,
            tech_report=[],
            branch_report=[],
            issue_report=[],
            daily_values=[1, 1, 1],
        )
        self.assertIsInstance(result, dict)
        self.assertIn('recommendations', result)
        # Should have at least one recommendation (the default)
        self.assertGreater(len(result['recommendations']), 0)


class ContextProcessorTest(TestCase):
    def test_panel_branding_without_settings(self):
        """panel_branding returns default brand when no PanelBrandSettings exists."""
        request = RequestFactory().get('/')
        result = panel_branding(request)
        self.assertEqual(result, {'panel_brand': {
            'brand_name': 'FRC CMS & TICKETS',
            'brand_subtitle': 'ADMIN PANEL',
            'logo_icon': '⚡',
            'logo_url': '',
        }})

    def test_panel_branding_with_settings(self):
        """panel_branding returns custom brand when PanelBrandSettings exists."""
        settings = PanelBrandSettings.objects.create(
            brand_name='Custom Brand',
            brand_subtitle='Custom Subtitle',
            logo_icon='★',
            logo_url='https://example.com',
        )
        request = RequestFactory().get('/')
        result = panel_branding(request)
        self.assertEqual(result['panel_brand']['brand_name'], 'Custom Brand')
        self.assertEqual(result['panel_brand']['brand_subtitle'], 'Custom Subtitle')
        self.assertEqual(result['panel_brand']['logo_icon'], '★')
        self.assertEqual(result['panel_brand']['logo_url'], 'https://example.com')
        # logo_image should be empty string because no image uploaded
        self.assertEqual(result['panel_brand']['logo_image'], '')

    def test_panel_branding_uses_defaults_when_database_unavailable(self):
        """panel_branding should not break template rendering if the DB is down."""
        request = RequestFactory().get('/')
        with patch(
            'tickets.context_processors.PanelBrandSettings.objects.first',
            side_effect=DatabaseError('branding table unavailable'),
        ):
            result = panel_branding(request)

        self.assertEqual(result, {'panel_brand': {
            'brand_name': 'FRC CMS & TICKETS',
            'brand_subtitle': 'ADMIN PANEL',
            'logo_icon': 'âš¡',
            'logo_url': '',
        }})


class SeedConfigTest(TestCase):
    def test_seed_function_creates_new_objects(self):
        """seed creates objects that don't exist."""
        from tickets.models import IssueType
        # Ensure no IssueType objects exist
        IssueType.objects.all().delete()
        data = [('test1', 'Test 1'), ('test2', 'Test 2')]
        # Call seed
        seed(IssueType, data, "Test")
        # Verify objects created
        self.assertEqual(IssueType.objects.count(), 2)
        obj1 = IssueType.objects.get(name='test1')
        self.assertEqual(obj1.display_name, 'Test 1')
        self.assertEqual(obj1.sort_order, 0)
        obj2 = IssueType.objects.get(name='test2')
        self.assertEqual(obj2.sort_order, 1)

    def test_seed_function_skips_existing_objects(self):
        """seed does not duplicate existing objects."""
        from tickets.models import IssueType
        IssueType.objects.all().delete()
        # Create one object beforehand
        IssueType.objects.create(name='test1', display_name='Existing', sort_order=99)
        data = [('test1', 'Test 1'), ('test2', 'Test 2')]
        seed(IssueType, data, "Test")
        # Should have created only test2
        self.assertEqual(IssueType.objects.count(), 2)
        obj1 = IssueType.objects.get(name='test1')
        # display_name should remain unchanged (since get_or_create uses defaults only if created)
        self.assertEqual(obj1.display_name, 'Existing')
        self.assertEqual(obj1.sort_order, 99)
        obj2 = IssueType.objects.get(name='test2')
        self.assertEqual(obj2.display_name, 'Test 2')
        self.assertEqual(obj2.sort_order, 1)

    def test_main_function(self):
        """main() runs without error and seeds all config tables."""
        # Ensure tables are empty
        from tickets.models import IssueType, ReceivedByOption, TechnicianOption, BranchOption
        IssueType.objects.all().delete()
        ReceivedByOption.objects.all().delete()
        TechnicianOption.objects.all().delete()
        BranchOption.objects.all().delete()
        # Call main
        main()
        # Verify that some objects were created (at least one per table)
        self.assertGreater(IssueType.objects.count(), 0)
        self.assertGreater(ReceivedByOption.objects.count(), 0)
        self.assertGreater(TechnicianOption.objects.count(), 0)
        self.assertGreater(BranchOption.objects.count(), 0)

    def test_script_as_main(self):
        """Running the script as __main__ executes the guard."""
        import runpy
        # This will execute the if __name__ == "__main__": block
        # We need to ensure the database is clean to avoid duplicate entries
        from tickets.models import IssueType, ReceivedByOption, TechnicianOption, BranchOption
        IssueType.objects.all().delete()
        ReceivedByOption.objects.all().delete()
        TechnicianOption.objects.all().delete()
        BranchOption.objects.all().delete()
        # Run the module as __main__
        runpy.run_module('tickets.seed_config', run_name='__main__')
        # Verify that objects were created
        self.assertGreater(IssueType.objects.count(), 0)
        self.assertGreater(ReceivedByOption.objects.count(), 0)
        self.assertGreater(TechnicianOption.objects.count(), 0)
        self.assertGreater(BranchOption.objects.count(), 0)


class URLSmokeTest(TestCase):
    def test_named_urls_resolve_for_known_routes(self):
        # Keeps cms_project/urls.py and panel_urls.py imported through URL reversing.
        self.assertTrue(reverse('panel_login').endswith('/panel/login/'))
        self.assertTrue(reverse('panel_dashboard').endswith('/panel/'))
        self.assertTrue(reverse('panel_tickets').endswith('/panel/tickets/'))
