from django.urls import path
from . import panel_views

urlpatterns = [
    # Auth
    path('login/', panel_views.panel_login, name='panel_login'),
    path('logout/', panel_views.panel_logout, name='panel_logout'),

    # Dashboard
    path('', panel_views.panel_dashboard, name='panel_dashboard'),
    path('dashboard/data/', panel_views.panel_dashboard_data, name='panel_dashboard_data'),

    # Tickets
    path('tickets/', panel_views.panel_tickets, name='panel_tickets'),
    path('partners/', panel_views.panel_partner_tickets, name='panel_partner_tickets'),
    path('tickets/add/', panel_views.panel_add_ticket, name='panel_add_ticket'),
    path('tickets/edit/<int:pk>/', panel_views.panel_edit_ticket, name='panel_edit_ticket'),
    path('tickets/delete/<int:pk>/', panel_views.panel_delete_ticket, name='panel_delete_ticket'),
    path('tickets/detail/<int:pk>/', panel_views.panel_ticket_detail, name='panel_ticket_detail'),
    path('tickets/status/<int:pk>/', panel_views.panel_update_status, name='panel_update_status'),
    path('tickets/remark/<int:pk>/', panel_views.panel_add_remark, name='panel_add_remark'),

    # Reports
    path('reports/', panel_views.panel_reports, name='panel_reports'),
    path('reports/export/', panel_views.panel_export_csv, name='panel_export_csv'),
    path('new-users/', panel_views.panel_new_user_tracking, name='panel_new_user_tracking'),

    # Users
    path('users/', panel_views.panel_users, name='panel_users'),
    path('users/add/', panel_views.panel_add_user, name='panel_add_user'),
    path('users/edit/<int:pk>/', panel_views.panel_edit_user, name='panel_edit_user'),
    path('users/delete/<int:pk>/', panel_views.panel_delete_user, name='panel_delete_user'),

    # Settings
    path('settings/', panel_views.panel_settings, name='panel_settings'),

    # Config CRUD (issue, received_by, technician, branch)
    path('config/<str:config_type>/add/', panel_views.config_add, name='config_add'),
    path('config/<str:config_type>/edit/<int:pk>/', panel_views.config_edit, name='config_edit'),
    path('config/<str:config_type>/delete/<int:pk>/', panel_views.config_delete, name='config_delete'),
]
