from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views, reports

app_name = 'core'

urlpatterns = [
    path('logout/', LogoutView.as_view(next_page='two_factor:login'), name='logout'),
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Admin Dashboard & Management
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('manage-users/', views.ManageUsersView.as_view(), name='manage_users'),
    path('manage-users/add/', views.UserCreateView.as_view(), name='user_create'),
    path('manage-users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('manage-users/<int:pk>/toggle/', views.UserDeactivateView.as_view(), name='user_toggle'),
    path('manage-users/<int:pk>/reset/', views.UserPasswordResetView.as_view(), name='user_reset_pwd'),
    path('manage-expenses/', views.ManageExpensesView.as_view(), name='manage_expenses'),
    path('manage-caisses/', views.ManageCaissesView.as_view(), name='manage_caisses'),
    path('manage-reports/', views.ManageReportsView.as_view(), name='manage_reports'),
    path('manage-commissions/', views.ManageCommissionsView.as_view(), name='manage_commissions'),
    path('manage-taux/', views.ManageTauxView.as_view(), name='manage_taux'),
    
    # Agent Dashboard
    path('agent-dashboard/', views.AgentDashboardView.as_view(), name='agent_dashboard'),
    
    # Partner Dashboards
    path('associe-dashboard/', views.AssocieDashboardView.as_view(), name='associe_dashboard'),
    path('investisseur-dashboard/', views.InvestisseurDashboardView.as_view(), name='investisseur_dashboard'),
    
    # User Profile
    path('mon-profil/', views.UserProfileView.as_view(), name='user_profile'),
    
    # Caisse Operations
    path('caisse/open/', views.OpenSessionView.as_view(), name='open_session'),
    path('caisse/close/', views.CloseSessionView.as_view(), name='close_session'),
    
    # New Enhanced Features
    path('agent-performance/', views.AgentPerformanceView.as_view(), name='agent_performance'),
    path('commission-tracking/', views.CommissionTrackingView.as_view(), name='commission_tracking'),
    path('partner-balance/', views.PartnerBalanceView.as_view(), name='partner_balance'),
    path('contract/<int:contract_id>/', views.PartnerContractDetailView.as_view(), name='contract_detail'),
    path('audit-log/', views.AuditLogView.as_view(), name='audit_log'),
    
    # System Management (Phase 1 gaps)
    path('system-settings/', views.SystemSettingsView.as_view(), name='system_settings'),
    path('transaction-management/', views.TransactionManagementView.as_view(), name='transaction_management'),
    path('transaction/<int:transaction_id>/edit/', views.TransactionEditView.as_view(), name='transaction_edit'),
    path('export/transactions/csv/', views.ExportTransactionsCsvView.as_view(), name='export_csv'),
    path('export/transactions/excel/', views.export_transactions_excel, name='export_excel'),

    # Investor & Associate Management (Admin)
    path('manage-investor-gains/', views.ManageInvestorGainsView.as_view(), name='manage_investor_gains'),
    path('manage-associate-reports/', views.ManageAssociateReportsView.as_view(), name='manage_associate_reports'),

    # REST API Endpoints
    path('api/transactions/', views.TransactionListCreateAPIView.as_view(), name='api_transactions'),
    path('api/transactions/<int:transaction_id>/', views.TransactionDetailAPIView.as_view(), name='api_transaction_detail'),
    path('api/system-settings/', views.SystemSettingsAPIView.as_view(), name='api_system_settings'),
    
    # HTMX and actions
    path('calculate-fee/', views.calculate_fee, name='calculate_fee'),
    path('process-transaction/', views.process_transaction, name='process_transaction'),
    
    # Reports
    path('report/<str:period>/', reports.generate_report, name='generate_report'),
]
