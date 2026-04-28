from django.contrib import admin
from .models import (
    Ticket, TicketRemark, IssueType, ReceivedByOption, TechnicianOption, BranchOption,
    PanelBrandSettings, PartnerOption,
)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['sn', 'date', 'user_name', 'partner_user_name', 'customer_id', 'cell_no',
                    'issue', 'received_by', 'technician_name', 'technician_assigned_at',
                    'status', 'is_new_user', 'new_user_id', 'solved_at',
                    'forwarded_to', 'forwarded_at', 'branch']
    list_filter = ['status', 'is_new_user', 'branch', 'issue', 'received_by', 'technician_name']
    search_fields = ['user_name', 'partner_user_name', 'customer_id', 'cell_no', 'new_user_id', 'remarks']
    list_editable = ['status', 'technician_name']
    list_per_page = 50
    date_hierarchy = 'date'
    ordering = ['-date', '-time']

@admin.register(IssueType)
class IssueTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'sort_order']
    list_editable = ['display_name', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']

@admin.register(ReceivedByOption)
class ReceivedByOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'sort_order']
    list_editable = ['display_name', 'is_active', 'sort_order']
    list_filter = ['is_active']

@admin.register(TechnicianOption)
class TechnicianOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'sort_order']
    list_editable = ['display_name', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']

@admin.register(BranchOption)
class BranchOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'monthly_target', 'is_active', 'sort_order']
    list_editable = ['display_name', 'monthly_target', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']

@admin.register(PartnerOption)
class PartnerOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'sort_order']
    list_editable = ['display_name', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']

@admin.register(PanelBrandSettings)
class PanelBrandSettingsAdmin(admin.ModelAdmin):
    list_display = ['brand_name', 'brand_subtitle', 'logo_icon', 'logo_url', 'updated_at']

@admin.register(TicketRemark)
class TicketRemarkAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'status', 'remark', 'created_by', 'created_at']
    list_filter = ['status', 'created_by']
    search_fields = ['remark', 'ticket__user_name']
    ordering = ['-created_at']
