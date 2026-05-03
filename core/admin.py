from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    Devise,
    ZoneTarif,
    Tarif,
    AgentProfile,
    Caisse,
    Transaction,
    Depense,
    ContratPartenaire,
    PaiementPartenaire,
    SessionCaisse,
    Commission,
    AgentActivityLog,
    AgentPerformanceMetrics,
    SystemSettings,
    TransactionAudit,
    APIToken,
)
from simple_history.admin import SimpleHistoryAdmin

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'role', 'telephone', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Supplémentaires', {'fields': ('role', 'telephone')}),
    )

@admin.register(Devise)
class DeviseAdmin(admin.ModelAdmin):
    list_display = ('code', 'taux_reference_usd')

@admin.register(ZoneTarif)
class ZoneTarifAdmin(admin.ModelAdmin):
    list_display = ('nom',)

@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = ('zone', 'montant_min', 'montant_max', 'frais_fixe')
    list_filter = ('zone',)

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'commission_pourcentage')

@admin.register(Caisse)
class CaisseAdmin(admin.ModelAdmin):
    list_display = ('agent', 'solde', 'devise')

@admin.register(SessionCaisse)
class SessionCaisseAdmin(admin.ModelAdmin):
    list_display = ('agent', 'date_ouverture', 'date_fermeture', 'solde_initial', 'solde_final_theorique', 'cash_declare', 'ecart', 'statut')
    list_filter = ('statut', 'agent')
    search_fields = ('agent__username',)

@admin.register(Transaction)
class TransactionAdmin(SimpleHistoryAdmin):
    list_display = ('numero_transaction', 'date', 'agent', 'type_operation', 'montant', 'devise_origine', 'statut')
    list_filter = ('type_operation', 'statut', 'devise_origine', 'agent')
    search_fields = ('numero_transaction', 'agent__username')

@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ('motif', 'date', 'montant', 'devise', 'categorie', 'enregistre_par')
    list_filter = ('categorie', 'devise', 'enregistre_par')

@admin.register(ContratPartenaire)
class ContratPartenaireAdmin(admin.ModelAdmin):
    list_display = ('partenaire', 'type_contrat', 'montant_engage', 'devise', 'montant_paye', 'statut')
    list_filter = ('type_contrat', 'statut')

@admin.register(PaiementPartenaire)
class PaiementPartenaireAdmin(admin.ModelAdmin):
    list_display = ('contrat', 'date', 'montant')

@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('agent', 'transaction', 'montant_commission', 'pourcentage', 'statut_paiement', 'date_paiement')
    list_filter = ('statut_paiement', 'agent')
    search_fields = ('agent__username', 'transaction__numero_transaction')

@admin.register(AgentActivityLog)
class AgentActivityLogAdmin(admin.ModelAdmin):
    list_display = ('agent', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'agent')
    search_fields = ('agent__username', 'ip_address', 'user_agent')

@admin.register(AgentPerformanceMetrics)
class AgentPerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ('agent', 'date', 'total_transactions', 'total_volume', 'total_fees', 'total_commissions')
    list_filter = ('date', 'agent')
    search_fields = ('agent__username',)

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'updated_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        """Prevent adding multiple settings records"""
        return not SystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False

@admin.register(TransactionAudit)
class TransactionAuditAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('transaction__numero_transaction', 'performed_by__username')
    readonly_fields = ('created_at', 'old_values', 'new_values', 'ip_address', 'user_agent')

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'created_at', 'last_used', 'expires_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'token')
    readonly_fields = ('token', 'created_at', 'last_used')
