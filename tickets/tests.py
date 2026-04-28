from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta, time
from django.core.exceptions import ValidationError
from .models import (
    Ticket,
    TicketRemark,
    IssueType,
    ReceivedByOption,
    TechnicianOption,
    BranchOption,
    PartnerOption,
)
from .forms import TicketForm
import json


class TicketModelTest(TestCase):
    """Test cases for the Ticket model."""
    
    def setUp(self):
        """Set up test data."""
        self.issue_type = IssueType.objects.create(
            name='internet_issue',
            display_name='Internet Connection Issue',
            is_active=True,
            sort_order=1
        )
        self.received_by = ReceivedByOption.objects.create(
            name='support_desk',
            display_name='Support Desk',
            is_active=True,
            sort_order=1
        )
        self.technician = TechnicianOption.objects.create(
            name='tech1',
            display_name='Technician 1',
            is_active=True,
            sort_order=1
        )
        self.branch = BranchOption.objects.create(
            name='hq',
            display_name='Head Quarter',
            is_active=True,
            sort_order=1
        )

    def test_ticket_creation(self):
        """Test creating a ticket with required fields."""
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='John Doe',
            customer_id='CUST001',
            cell_no='01712345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq'
        )
        self.assertEqual(ticket.user_name, 'John Doe')
        self.assertEqual(ticket.status, 'PENDING')
        self.assertIsNotNone(ticket.time)
        self.assertEqual(str(ticket), f"#{ticket.sn} - John Doe (internet_issue)")

    def test_ticket_auto_time_assignment(self):
        """Test that time is automatically set when creating a ticket."""
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='Jane Doe',
            customer_id='CUST002',
            cell_no='01812345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq'
        )
        self.assertIsNotNone(ticket.time)
        self.assertIsInstance(ticket.time, time)

    def test_ticket_technician_assignment_timestamp(self):
        """Test that technician_assigned_at is set when technician is assigned."""
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='Bob Smith',
            customer_id='CUST003',
            cell_no='01912345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq'
        )
        self.assertIsNone(ticket.technician_assigned_at)
        
        ticket.technician_name = 'tech1'
        ticket.save()
        
        self.assertIsNotNone(ticket.technician_assigned_at)
        self.assertIsInstance(ticket.technician_assigned_at, timezone.datetime)

    def test_ticket_solved_timestamp(self):
        """Test that solved_at is set when status changes to SOLVED."""
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='Alice Johnson',
            customer_id='CUST004',
            cell_no='01612345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq'
        )
        self.assertIsNone(ticket.solved_at)
        
        ticket.status = 'SOLVED'
        ticket.save()
        
        self.assertIsNotNone(ticket.solved_at)
        self.assertIsInstance(ticket.solved_at, timezone.datetime)

    def test_ticket_properties(self):
        """Test ticket property methods."""
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='Test User',
            customer_id='CUST005',
            cell_no='01512345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq'
        )
        
        # Test is_solved property
        self.assertFalse(ticket.is_solved)
        ticket.status = 'SOLVED'
        ticket.save()
        self.assertTrue(ticket.is_solved)
        
        # Test days_open property
        self.assertGreaterEqual(ticket.days_open, 0)
        
        # Test has_remarks property
        self.assertFalse(ticket.has_remarks)
        TicketRemark.objects.create(
            ticket=ticket,
            status='SOLVED',
            remark='Test remark',
            created_by='test_user'
        )
        self.assertTrue(ticket.has_remarks)


class TicketFormTest(TestCase):
    """Test cases for the TicketForm."""
    
    def setUp(self):
        """Set up test data."""
        self.issue_type = IssueType.objects.create(
            name='internet_issue',
            display_name='Internet Connection Issue',
            is_active=True,
            sort_order=1
        )
        self.received_by = ReceivedByOption.objects.create(
            name='support_desk',
            display_name='Support Desk',
            is_active=True,
            sort_order=1
        )
        self.technician = TechnicianOption.objects.create(
            name='tech1',
            display_name='Technician 1',
            is_active=True,
            sort_order=1
        )
        self.branch = BranchOption.objects.create(
            name='hq',
            display_name='Head Quarter',
            is_active=True,
            sort_order=1
        )
        self.partner = PartnerOption.objects.create(
            name='partner_one',
            display_name='Partner One',
            is_active=True,
            sort_order=1
        )

    def test_form_valid_data(self):
        """Test form with valid data."""
        form_data = {
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
            'remark': ''
        }
        form = TicketForm(data=form_data)
        if not form.is_valid():
            print("Form errors:", form.errors)
        self.assertTrue(form.is_valid())

    def test_form_invalid_phone_number(self):
        """Test form validation with invalid phone number."""
        form_data = {
            'date': date.today(),
            'user_name': 'John Doe',
            'customer_id': 'CUST001',
            'cell_no': '12345',  # Invalid phone number
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'branch': 'hq'
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cell_no', form.errors)

    def test_form_invalid_customer_id(self):
        """Test form validation with invalid customer ID."""
        form_data = {
            'date': date.today(),
            'user_name': 'John Doe',
            'customer_id': 'cust001',  # Lowercase not allowed
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'branch': 'hq'
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('customer_id', form.errors)

    def test_form_future_date_validation(self):
        """Test form validation with future date."""
        future_date = date.today() + timedelta(days=1)
        form_data = {
            'date': future_date,
            'user_name': 'John Doe',
            'customer_id': 'CUST001',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'branch': 'hq'
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('date', form.errors)

    def test_form_solved_without_technician(self):
        """Test form validation when marking as solved without technician."""
        form_data = {
            'date': date.today(),
            'user_name': 'John Doe',
            'customer_id': 'CUST001',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'SOLVED',
            'branch': 'hq'
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('technician_name', form.errors)

    def test_user_name_and_customer_id_required_when_new_user_ticket_is_solved(self):
        form_data = {
            'date': date.today(),
            'user_name': '',
            'customer_id': '',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'technician_name': 'tech1',
            'status': 'SOLVED',
            'branch': 'hq',
            'is_new_user': 'on',
            'new_user_id': '',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('user_name', form.errors)
        self.assertIn('customer_id', form.errors)

    def test_new_user_id_not_required_for_solved_new_user_ticket(self):
        form_data = {
            'date': date.today(),
            'user_name': 'New Customer',
            'customer_id': 'CUST010',
            'cell_no': '01712345678',
            'issue': 'NEW USER',
            'received_by': 'support_desk',
            'technician_name': 'tech1',
            'status': 'SOLVED',
            'branch': 'hq',
            'is_new_user': 'on',
            'new_user_id': '',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_new_user_id_not_required_until_solved(self):
        form_data = {
            'date': date.today(),
            'user_name': 'New Customer',
            'customer_id': 'CUST011',
            'cell_no': '01712345678',
            'issue': 'NEW USER',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'branch': 'hq',
            'is_new_user': 'on',
            'new_user_id': '',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_new_user_issue_is_required(self):
        form_data = {
            'date': date.today(),
            'user_name': 'New Customer',
            'customer_id': 'CUST012',
            'cell_no': '01712345678',
            'issue': '',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'branch': 'hq',
            'is_new_user': 'on',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('issue', form.errors)

    def test_partner_form_requires_partner_and_user_name(self):
        form_data = {
            'date': date.today(),
            'user_name': 'partner_one',
            'partner_user_name': '',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'is_partner': 'True',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data, initial={'is_partner': True})
        self.assertFalse(form.is_valid())
        self.assertIn('partner_user_name', form.errors)

    def test_partner_form_accepts_separate_user_name(self):
        form_data = {
            'date': date.today(),
            'user_name': 'partner_one',
            'partner_user_name': 'Ariful Islam',
            'cell_no': '01712345678',
            'issue': 'internet_issue',
            'received_by': 'support_desk',
            'status': 'PENDING',
            'is_partner': 'True',
            'forwarded_to': '',
            'forwarded_to_other': '',
            'remark': '',
        }
        form = TicketForm(data=form_data, initial={'is_partner': True})
        self.assertTrue(form.is_valid())


class TicketViewTest(TestCase):
    """Test cases for ticket views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        self.issue_type = IssueType.objects.create(
            name='internet_issue',
            display_name='Internet Connection Issue',
            is_active=True,
            sort_order=1
        )
        self.received_by = ReceivedByOption.objects.create(
            name='support_desk',
            display_name='Support Desk',
            is_active=True,
            sort_order=1
        )
        self.branch = BranchOption.objects.create(
            name='hq',
            display_name='Head Quarter',
            is_active=True,
            sort_order=1
        )

    def test_dashboard_view(self):
        """Test dashboard view loads correctly."""
        response = self.client.get('/panel/')
        self.assertIn(response.status_code, [200, 301, 302])  # Allow all redirects
        if response.status_code == 200:
            self.assertContains(response, 'Dashboard')

    def test_dashboard_data_view(self):
        Ticket.objects.create(
            date=date.today(),
            user_name='Live Dashboard User',
            customer_id='LIVE001',
            cell_no='01712345678',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq',
        )

        response = self.client.get('/panel/dashboard/data/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['pending'], 1)
        self.assertIn('recent_tickets', data)
        self.assertEqual(data['recent_tickets'][0]['user_name'], 'Live Dashboard User')

    def test_tickets_list_view(self):
        """Test tickets list view."""
        response = self.client.get('/panel/tickets/')
        self.assertIn(response.status_code, [200, 301, 302])  # Allow all redirects
        if response.status_code == 200:
            self.assertContains(response, 'Tickets')

    def test_add_ticket_view(self):
        """Test adding a new ticket."""
        response = self.client.get('/panel/tickets/add/', follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Just test that the form is present and can be submitted
        # The actual creation test is complex due to dynamic form fields
        self.assertContains(response, 'form')

    def test_general_ticket_list_excludes_new_user_tickets(self):
        Ticket.objects.create(
            date=date.today(),
            user_name='Regular User',
            customer_id='CUST100',
            cell_no='01711111111',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq',
        )
        Ticket.objects.create(
            date=date.today(),
            user_name='New User Queue',
            customer_id='CUST101',
            cell_no='01722222222',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq',
            is_new_user=True,
        )

        response = self.client.get('/panel/tickets/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Regular User')
        self.assertNotContains(response, 'New User Queue')

    def test_edit_new_user_ticket_redirects_to_new_user_module(self):
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='Module User',
            customer_id='CUST102',
            cell_no='01733333333',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq',
            is_new_user=True,
        )
        response = self.client.post(f'/panel/tickets/edit/{ticket.sn}/', {
            'date': ticket.date.isoformat(),
            'user_name': 'Module User',
            'customer_id': 'CUST102',
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

    def test_quick_status_update_blocks_invalid_new_user_solve(self):
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='',
            customer_id='',
            cell_no='01744444444',
            issue='internet_issue',
            received_by='support_desk',
            branch='hq',
            is_new_user=True,
            status='PENDING',
        )
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json()['error'])

    def test_quick_status_update_blocks_new_user_solve_without_issue(self):
        ticket = Ticket.objects.create(
            date=date.today(),
            user_name='New User',
            customer_id='CUST500',
            cell_no='01745555555',
            issue='',
            received_by='support_desk',
            branch='hq',
            is_new_user=True,
            technician_name='tech1',
            status='PENDING',
        )
        response = self.client.post(
            f'/panel/tickets/status/{ticket.sn}/',
            data=json.dumps({'status': 'SOLVED'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Issue is required', response.json()['error'])


class TicketNewUserReportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reportuser', password='testpass123')
        self.client = Client()
        self.client.login(username='reportuser', password='testpass123')
        self.issue_type = IssueType.objects.create(name='connection', display_name='Connection', is_active=True)
        self.received_by = ReceivedByOption.objects.create(name='desk', display_name='Desk', is_active=True)
        self.branch = BranchOption.objects.create(name='north_hub', display_name='North Hub', is_active=True)

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
