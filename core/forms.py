from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Depense, Caisse, CustomUser, Role, SystemSettings, Transaction, TransactionAudit

class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = ['montant', 'devise', 'motif', 'categorie', 'destination', 'commentaire', 'justificatif']
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control'}),
            'devise': forms.Select(attrs={'class': 'form-control'}),
            'motif': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.TextInput(attrs={'class': 'form-control'}),
            'destination': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CaisseAdjustmentForm(forms.Form):
    agent = forms.ModelChoiceField(queryset=CustomUser.objects.filter(caisse__isnull=False).distinct(), widget=forms.Select(attrs={'class': 'form-control'}))
    montant = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    type_ajustement = forms.ChoiceField(
        choices=[('ALLOCATION', 'Allocation de Fonds'), ('DEDUCTION', 'Déduction / Récupération')], 
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Type d'Opération"
    )
    commentaire = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

class CustomUserCreationAdminForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'telephone')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CustomUserChangeAdminForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'role', 'telephone', 'is_active')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'telephone', 'photo')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

class CloseSessionForm(forms.Form):
    cash_declare = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        label="Espèces comptées en fin de journée (Cash déclaré)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class SystemSettingsForm(forms.ModelForm):
    """Form for managing system settings"""
    class Meta:
        model = SystemSettings
        fields = [
            'company_name', 'company_phone', 'company_email', 'company_address',
            'default_commission_percentage', 'transaction_number_prefix',
            'enable_email_notifications', 'enable_sms_notifications', 'enable_api',
            'is_maintenance_mode', 'maintenance_message',
            'enable_audit_trail', 'audit_retention_days',
            'auto_reconcile_threshold', 'require_manager_approval'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'default_commission_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'transaction_number_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'enable_email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_api': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maintenance_message': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'enable_audit_trail': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'audit_retention_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'auto_reconcile_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'require_manager_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TransactionEditForm(forms.ModelForm):
    """Form for editing transaction details"""
    class Meta:
        model = Transaction
        fields = ['montant', 'frais_calcules', 'observation', 'statut', 'motif_annulation']
        widgets = {
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'frais_calcules': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'observation': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'motif_annulation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


class TransactionSearchForm(forms.Form):
    """Form for advanced transaction searching"""
    numero_transaction = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° Transaction'}))
    agent = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=Role.AGENT),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Agent"
    )
    type_operation = forms.ChoiceField(
        choices=[('', '--- Tous ---'), ('TRANSFERT', 'Transfert'), ('RETRAIT', 'Retrait')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    statut = forms.ChoiceField(
        choices=[('', '--- Tous ---'), ('COMPLETED', 'Terminé'), ('ANNULÉ', 'Annulé')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Date À partir de"
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Date Jusqu'à"
    )
    montant_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Montant min'}),
        label="Montant Minimum"
    )
    montant_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Montant max'}),
        label="Montant Maximum"
    )
