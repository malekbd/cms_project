import re
from django import forms
from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Ticket,
    IssueType,
    ReceivedByOption,
    TechnicianOption,
    BranchOption,
    PartnerOption,
    STATUS_CHOICES,
)

FORWARDED_TO_CHOICES = [
    ('', '--- Select ---'),
    ('ARIF', 'ARIF'),
    ('KHIRUL', 'KHIRUL'),
    ('ARMAN', 'ARMAN'),
    ('DIPANTO', 'DIPANTO'),
    ('RASHED', 'RASHED'),
    ('OTHER', 'OTHER'),
]

FORWARDED_TO_NAMES = [c[0] for c in FORWARDED_TO_CHOICES if c[0]]

NEW_USER_ISSUE_CHOICES = [
    ('', '--- Select Issue ---'),
    ('NEW USER', 'NEW USER'),
    ('RECONNECTION', 'RECONNECTION'),
    ('HOUSE SHIFTING', 'HOUSE SHIFTING'),
]

# Custom validators
phone_validator = RegexValidator(
    regex=r'^(?:\+?88)?01[3-9]\d{8}$',
    message="Enter a valid Bangladeshi mobile number"
)

customer_id_validator = RegexValidator(
    regex=r'^[A-Z0-9][A-Z0-9_-]{0,99}$',
    message="Customer ID must use uppercase letters, numbers, hyphens, or underscores only"
)


class TicketForm(forms.ModelForm):
    # Extra field — not on the model, used only when "OTHER" is picked
    forwarded_to_other = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter name...',
            'id': 'id_forwarded_to_other',
        }),
    )

    # Remark field for status-wise remarks
    remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Add a remark about this update...',
        }),
    )

    class Meta:
        model = Ticket
        fields = ['date', 'user_name', 'partner_user_name', 'customer_id', 'cell_no', 'issue',
                  'received_by', 'technician_name',
                  'status', 'forwarded_to', 'branch', 'is_partner',
                  'is_new_user', 'new_user_id']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'user_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Name', 'maxlength': 200}),
            'partner_user_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'User Name', 'maxlength': 200}),
            'customer_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer ID', 'maxlength': 100}),
            'cell_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cell Number', 'maxlength': 20}),
            'is_new_user': forms.CheckboxInput(attrs={'class': 'form-check-input new-user-toggle'}),
            'new_user_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'New User ID', 'maxlength': 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Detect partner status from data (POST), initial, or instance
        is_partner_form = (
            (self.data.get('is_partner') in ['True', 'on', True]) or
            self.initial.get('is_partner', False) or 
            (self.instance and getattr(self.instance, 'is_partner', False))
        )
        is_new_user_form = (
            (self.data.get('is_new_user') in ['True', 'true', 'on', True]) or
            self.initial.get('is_new_user', False) or
            (self.instance and getattr(self.instance, 'is_new_user', False))
        )

        # Fields are optional at the form level to allow custom validation in clean()
        self.fields['user_name'].required = False
        self.fields['partner_user_name'].required = False
        self.fields['customer_id'].required = False
        self.fields['issue'].required = False
        self.fields['received_by'].required = False
        self.fields['branch'].required = False
        self.fields['status'].required = False
        self.fields['status'].initial = 'PENDING'

        # Set max date to today
        now = timezone.now()
        current_date = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
        self.fields['date'].widget.attrs['max'] = current_date.isoformat()

        # Add manual validators
        self.fields['cell_no'].validators = [phone_validator]
        self.fields['customer_id'].validators = [customer_id_validator]
        self.fields['forwarded_to_other'].validators = [
            MaxLengthValidator(100, message="Name cannot exceed 100 characters")
        ]

        # --- Dropdown Configuration ---
        self.fields['forwarded_to'] = forms.ChoiceField(
            choices=FORWARDED_TO_CHOICES,
            required=False,
            widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_forwarded_to', 'onchange': 'toggleForwardedOther(this)'}),
        )

        self.fields['issue'] = forms.ChoiceField(
            choices=[('', '— Select Issue —')] + [(opt.name, opt.display_name) for opt in IssueType.objects.filter(is_active=True)],
            required=False, widget=forms.Select(attrs={'class': 'form-select'})
        )

        self.fields['received_by'] = forms.ChoiceField(
            choices=[('', '— Select —')] + [(opt.name, opt.display_name) for opt in ReceivedByOption.objects.filter(is_active=True)],
            required=False, widget=forms.Select(attrs={'class': 'form-select'})
        )

        self.fields['technician_name'] = forms.ChoiceField(
            choices=[('', '— Select Technician —')] + [(opt.name, opt.display_name) for opt in TechnicianOption.objects.filter(is_active=True)],
            required=False, widget=forms.Select(attrs={'class': 'form-select'})
        )

        self.fields['branch'] = forms.ChoiceField(
            choices=[('', '— Select Branch —')] + [(opt.name, opt.display_name) for opt in BranchOption.objects.filter(is_active=True)],
            required=False, widget=forms.Select(attrs={'class': 'form-select'})
        )

        # Dynamic Partner Logic: If it is a partner ticket, change user_name to ChoiceField
        if is_partner_form:
            self.fields['user_name'] = forms.ChoiceField(
                choices=[('', '— Select Partner —')] + [(opt.name, opt.display_name) for opt in PartnerOption.objects.filter(is_active=True)],
                widget=forms.Select(attrs={'class': 'form-select'})
            )

        elif is_new_user_form:
            new_user_issue_choices = list(NEW_USER_ISSUE_CHOICES)
            current_issue = (self.instance.issue or '').strip() if self.instance else ''
            if current_issue and current_issue not in dict(new_user_issue_choices):
                new_user_issue_choices.append((current_issue, current_issue))
            self.fields['issue'] = forms.ChoiceField(
                choices=new_user_issue_choices,
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'})
            )

    def clean_date(self):
        ticket_date = self.cleaned_data.get('date')
        now = timezone.now()
        current_date = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
        if ticket_date and ticket_date > current_date:
            raise ValidationError("Date cannot be in the future")
        return ticket_date

    def clean_customer_id(self):
        customer_id = (self.cleaned_data.get('customer_id') or '').strip()
        if customer_id and not re.match(r'^[A-Z0-9][A-Z0-9_-]{0,99}$', customer_id):
            raise ValidationError("Customer ID must use uppercase letters, numbers, hyphens, or underscores only")
        return customer_id

    def clean_cell_no(self):
        cell_no = self.cleaned_data.get('cell_no', '').strip()
        if cell_no:
            if cell_no.startswith('+880'):
                cell_no = cell_no[3:]
            elif cell_no.startswith('88') and len(cell_no) > 5:
                cell_no = cell_no[2:]
        return cell_no

    def clean(self):
        cleaned = super().clean()
        fwd = cleaned.get('forwarded_to', '')
        fwd_other = cleaned.get('forwarded_to_other', '').strip()

        if fwd == 'OTHER':
            if not fwd_other:
                self.add_error('forwarded_to_other', 'Please enter the name.')
            else:
                cleaned['forwarded_to'] = fwd_other.strip().upper()

        status = cleaned.get('status') or 'PENDING'
        cleaned['status'] = status
        technician = cleaned.get('technician_name')
        is_new_user = cleaned.get('is_new_user', False)
        is_partner = cleaned.get('is_partner', False)
        new_user_id = (cleaned.get('new_user_id') or '').strip()
        
        user_name = (cleaned.get('user_name') or '').strip()
        partner_user_name = (cleaned.get('partner_user_name') or '').strip()
        customer_id = (cleaned.get('customer_id') or '').strip()
        issue = cleaned.get('issue', '')

        # 1. Partner Validation
        if is_partner:
            if not user_name:
                self.add_error('user_name', 'Partner Name is required.')
            if not partner_user_name:
                self.add_error('partner_user_name', 'User Name is required.')
            if not issue:
                self.add_error('issue', 'Issue is required.')
        
        # 2. Existing User Validation
        elif not is_new_user:
            if not user_name:
                self.add_error('user_name', 'Customer Name is required.')
            if not customer_id:
                self.add_error('customer_id', 'Customer ID is required.')
            if not issue:
                self.add_error('issue', 'Issue is required.')
        
        # 3. New User Validation (Logic for SOLVED state)
        else:
            if not issue:
                self.add_error('issue', 'Issue is required for new user tickets.')
            if status == 'SOLVED':
                if not user_name:
                    self.add_error('user_name', 'Customer Name is required when marking as SOLVED.')
                if not customer_id:
                    self.add_error('customer_id', 'Customer ID is required when marking as SOLVED.')

        # 4. Mandatory Technician for Solved Tickets (Excluding Partners)
        if status == 'SOLVED' and not is_partner and not technician:
            self.add_error('technician_name', 'Technician must be assigned when marking as SOLVED.')

        cleaned['partner_user_name'] = partner_user_name or None
        cleaned['new_user_id'] = new_user_id or None
        return cleaned
