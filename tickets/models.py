from django.db import models
from django.utils import timezone
from typing import Optional, List, Dict, Any
from django.db.models import QuerySet


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURABLE OPTION MODELS (managed from Admin Panel -> Settings)
# ═══════════════════════════════════════════════════════════════════════════

class IssueType(models.Model):
    """
    Configurable issue types for support tickets.
    
    This model allows administrators to define different types of issues
    that can be selected when creating or editing tickets. Issue types
    can be activated/deactivated and sorted for better organization.
    
    Attributes:
        name: Internal identifier for the issue type (unique)
        display_name: User-friendly name shown in dropdowns
        is_active: Whether this issue type is available for selection
        sort_order: Order in which this issue type appears in lists
    """
    name: str = models.CharField(max_length=100, unique=True, help_text="Internal identifier for the issue type")
    display_name: str = models.CharField(max_length=100, help_text="User-friendly name shown in dropdowns")
    is_active: bool = models.BooleanField(default=True, help_text="Whether this issue type is available for selection")
    sort_order: int = models.IntegerField(default=0, help_text="Order in which this issue type appears in lists")

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Issue Type'
        verbose_name_plural = 'Issue Types'

    def __str__(self) -> str:
        """Return the display name for admin interface."""
        return self.display_name

    @classmethod
    def get_active_choices(cls) -> List[tuple]:
        """Get all active issue types as choice tuples."""
        return [(obj.name, obj.display_name) for obj in cls.objects.filter(is_active=True)]


class ReceivedByOption(models.Model):
    """Configurable 'received by' departments/persons."""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Received By Option'

    def __str__(self):
        return self.display_name


class TechnicianOption(models.Model):
    """Configurable technician names."""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Technician'

    def __str__(self):
        return self.display_name


class BranchOption(models.Model):
    """Configurable branch locations with monthly targets."""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    monthly_target = models.IntegerField(default=0, help_text="Set the monthly new user target for this branch")

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Branch'

    def __str__(self):
        return self.display_name


class PartnerOption(models.Model):
    """Configurable partner names."""
    name = models.CharField(max_length=200, unique=True)
    display_name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Partner'

    def __str__(self):
        return self.display_name


class PanelBrandSettings(models.Model):
    """Global branding options for the panel sidebar/dashboard."""
    brand_name = models.CharField(max_length=120, default='FRC CMS & TICKETS')
    brand_subtitle = models.CharField(max_length=120, default='ADMIN PANEL')
    logo_icon = models.CharField(max_length=10, default='⚡')
    logo_image = models.ImageField(upload_to='branding/', blank=True, null=True)
    logo_url = models.URLField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Panel Brand Setting'
        verbose_name_plural = 'Panel Brand Settings'

    def __str__(self):
        return self.brand_name


# ═══════════════════════════════════════════════════════════════════════════
# STATUS CHOICES (kept hardcoded — these are system-level)
# ═══════════════════════════════════════════════════════════════════════════

STATUS_CHOICES = [
    ('SOLVED', 'Solved'),
    ('PENDING', 'Pending'),
    ('TIME TAKEN', 'Time Taken'),
    ('No Response', 'No Response'),
]


# ═══════════════════════════════════════════════════════════════════════════
# TICKET MODEL
# ═══════════════════════════════════════════════════════════════════════════

class Ticket(models.Model):
    """
    Main ticket model for customer support tracking.
    
    This model represents a customer support ticket with comprehensive tracking
    of status changes, assignments, and resolution details. The system automatically
    manages timestamps for key events and maintains a complete audit trail.
    """
    sn: int = models.AutoField(primary_key=True, help_text="Auto-incrementing serial number")
    date: 'datetime.date' = models.DateField(help_text="Date when the ticket was created/occurred")
    user_name: str = models.CharField(max_length=200, help_text="Name of the customer who raised the ticket")
    partner_user_name: Optional[str] = models.CharField(max_length=200, blank=True, null=True, help_text="End-user name for partner tickets")
    customer_id: str = models.CharField(max_length=100, help_text="Unique identifier for the customer")
    cell_no: str = models.CharField(max_length=20, help_text="Contact phone number for the customer")
    issue: str = models.CharField(max_length=100, help_text="Type/category of the issue")
    received_by: str = models.CharField(max_length=100, help_text="Who initially received the ticket")
    time: Optional['datetime.time'] = models.TimeField(blank=True, null=True, help_text="Time when the ticket was created")
    technician_name: Optional[str] = models.CharField(max_length=100, blank=True, null=True, help_text="Assigned technician for resolution")
    technician_assigned_at: Optional['datetime.datetime'] = models.DateTimeField(blank=True, null=True, help_text="Timestamp when technician was assigned")
    status: str = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING', help_text="Current status of the ticket")
    solved_at: Optional['datetime.datetime'] = models.DateTimeField(blank=True, null=True, help_text="Timestamp when ticket was marked as solved")
    forwarded_to: Optional[str] = models.CharField(max_length=100, blank=True, null=True, help_text="Person/department the ticket was forwarded to")
    forwarded_at: Optional['datetime.datetime'] = models.DateTimeField(blank=True, null=True, help_text="Timestamp when ticket was forwarded")
    remarks: Optional[str] = models.TextField(blank=True, null=True, help_text="Additional notes about the ticket")
    is_partner: bool = models.BooleanField(default=False, help_text="Indicates if this is a partner ticket")
    is_new_user: bool = models.BooleanField(default=False, help_text="Indicates if this solved ticket added a new user")
    new_user_id: Optional[str] = models.CharField(max_length=100, blank=True, null=True, help_text="New user/customer identifier created after solving")
    branch: str = models.CharField(max_length=100, default='Head Quarter, Sirajganj', help_text="Branch location where the ticket originated")
    created_at: 'datetime.datetime' = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at: 'datetime.datetime' = models.DateTimeField(auto_now=True, help_text="Last modification timestamp")

    class Meta:
        ordering = ['-date', '-time']
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['cell_no']),
            models.Index(fields=['technician_name']),
            models.Index(fields=['branch']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_status = self.status
        self.__original_technician_name = self.technician_name
        self.__original_forwarded_to = self.forwarded_to

    def __str__(self) -> str:
        """Return a human-readable representation of the ticket."""
        return f"#{self.sn} - {self.user_name} ({self.issue})"

    @property
    def is_solved(self) -> bool:
        """Check if the ticket is marked as solved."""
        return self.status == 'SOLVED'

    @property
    def days_open(self) -> int:
        """Calculate how many days the ticket has been open."""
        now = timezone.now()
        current_date = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
        end_date = self.solved_at.date() if self.solved_at else current_date
        return (end_date - self.date).days

    @property
    def has_remarks(self) -> bool:
        """Check if the ticket has any remarks."""
        return self.ticket_remarks.exists()

    def get_latest_remark(self) -> Optional['TicketRemark']:
        """Get the most recent remark for this ticket."""
        return self.ticket_remarks.first()

    def save(self, *args, **kwargs):
        # Auto-set time to now if not provided (new ticket)
        if not self.time:
            self.time = timezone.now().time()

        is_new = self.pk is None

        # Auto-set technician_assigned_at when technician is first assigned
        if self.technician_name and not self.technician_assigned_at:
            if is_new or self.__original_technician_name != self.technician_name:
                self.technician_assigned_at = timezone.now()

        # Auto-set solved_at when status changes to SOLVED
        if self.status == 'SOLVED' and not self.solved_at:
            if is_new or self.__original_status != 'SOLVED':
                self.solved_at = timezone.now()

        # Reset solved_at if status changes away from SOLVED
        if self.status != 'SOLVED':
            self.solved_at = None

        # Auto-set forwarded_at when forwarded_to is first assigned
        if self.forwarded_to and not self.forwarded_at:
            if is_new or self.__original_forwarded_to != self.forwarded_to:
                self.forwarded_at = timezone.now()

        # Reset forwarded_at if forwarded_to is cleared
        if not self.forwarded_to:
            self.forwarded_at = None

        super().save(*args, **kwargs)
        
        # update originals
        self.__original_status = self.status
        self.__original_technician_name = self.technician_name
        self.__original_forwarded_to = self.forwarded_to


# ═══════════════════════════════════════════════════════════════════════════
# TICKET REMARKS (status-wise notes / history)
# ═══════════════════════════════════════════════════════════════════════════

class TicketRemark(models.Model):
    """Individual remark attached to a ticket, tagged with the status at that time."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='ticket_remarks')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    remark = models.TextField()
    created_by = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Remark on #{self.ticket_id} [{self.status}] - {self.remark[:50]}"
