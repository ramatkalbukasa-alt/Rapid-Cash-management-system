from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from simple_history.models import HistoricalRecords

class Role(models.TextChoices):
    ADMIN = 'ADMINISTRATEUR', _('Administrateur')
    AGENT = 'AGENT', _('Agent')
    ASSOCIE = 'ASSOCIE', _('Associé')
    INVESTISSEUR = 'INVESTISSEUR', _('Investisseur')

class CustomUser(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT, verbose_name=_("Rôle"))
    telephone = models.CharField(max_length=20, blank=True, verbose_name=_("Téléphone"))
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True, verbose_name=_("Photo de profil"))
    is_active = models.BooleanField(default=True, verbose_name=_("Compte actif"))
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

class Devise(models.Model):
    code = models.CharField(max_length=3, unique=True, verbose_name=_("Code devise (ex: USD, EUR)"))
    taux_reference_usd = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, 
                                             verbose_name=_("Taux par rapport à l'USD"))
    
    class Meta:
        verbose_name = _("Devise")
        verbose_name_plural = _("Devises")

    def __str__(self):
        return self.code

class ZoneTarif(models.Model):
    nom = models.CharField(max_length=50, unique=True, verbose_name=_("Nom de la zone (ex: Nord-Congo)"))

    class Meta:
        verbose_name = _("Zone Tarifaire")
        verbose_name_plural = _("Zones Tarifaires")

    def __str__(self):
        return self.nom

class Tarif(models.Model):
    zone = models.ForeignKey(ZoneTarif, on_delete=models.CASCADE, related_name='tarifs', verbose_name=_("Zone"))
    montant_min = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Montant Minimum"))
    montant_max = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Montant Maximum"))
    frais_fixe = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Frais Fixe"))

    class Meta:
        verbose_name = _("Tarif")
        verbose_name_plural = _("Tarifs")
        ordering = ['zone', 'montant_min']

    def __str__(self):
        return f"{self.zone.nom} : {self.montant_min} - {self.montant_max} -> {self.frais_fixe}"

class AgentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='agent_profile')
    commission_pourcentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name=_("Pourcentage de commission (%)"))

    class Meta:
        verbose_name = _("Profil Agent")
        verbose_name_plural = _("Profils Agents")

    def __str__(self):
        return f"Profil de l'agent {self.user.username}"

class Caisse(models.Model):
    agent = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='caisse', 
                                 limit_choices_to={'role__in': [Role.AGENT, Role.ADMIN]}, verbose_name=_("Agent"))
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name=_("Solde"))
    devise = models.ForeignKey(Devise, on_delete=models.RESTRICT, verbose_name=_("Devise de la caisse"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Caisse")
        verbose_name_plural = _("Caisses")

    def __str__(self):
        return f"Caisse de {self.agent.username} - {self.solde} {self.devise.code}"

class TypeOperation(models.TextChoices):
    TRANSFERT = 'TRANSFERT', _('Transfert')
    RETRAIT = 'RETRAIT', _('Retrait')

class StatutTransaction(models.TextChoices):
    COMPLETED = 'COMPLETED', _('Terminé')
    ANNULE = 'ANNULÉ', _('Annulé')

class Transaction(models.Model):
    numero_transaction = models.CharField(max_length=100, unique=True, verbose_name=_("N° Transaction"))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_("Date et Heure"))
    agent = models.ForeignKey(CustomUser, on_delete=models.RESTRICT, related_name='transactions', limit_choices_to={'role__in': [Role.AGENT, Role.ADMIN]}, verbose_name=_("Agent"))
    type_operation = models.CharField(max_length=20, choices=TypeOperation.choices, verbose_name=_("Type d'opération"))
    montant = models.DecimalField(max_digits=15, decimal_places=2, verbose_name=_("Montant"))
    devise_origine = models.ForeignKey(Devise, on_delete=models.RESTRICT, related_name="trans_origine", verbose_name=_("Devise d'origine"))
    
    # Financial calculations
    taux_conversion = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_("Taux appliqué"), help_text="Taux vers la devise de réf.")
    frais_calcules = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Frais calculés"))
    montant_reference = models.DecimalField(max_digits=15, decimal_places=2, verbose_name=_("Montant (Réf. USD)"), null=True, blank=True)
    frais_reference = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Frais (Réf. USD)"), null=True, blank=True)
    
    observation = models.TextField(blank=True, verbose_name=_("Observation"))
    statut = models.CharField(max_length=20, choices=StatutTransaction.choices, default=StatutTransaction.COMPLETED, verbose_name=_("Statut"))
    motif_annulation = models.TextField(blank=True, verbose_name=_("Motif d'annulation"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering = ['-date']

    def __str__(self):
        return f"{self.numero_transaction} - {self.type_operation} - {self.montant} {self.devise_origine.code}"

    def save(self, *args, **kwargs):
        if self.pk:
            old_instance = Transaction.objects.get(pk=self.pk)
            # If changing from COMPLETED to ANNULE
            if old_instance.statut == StatutTransaction.COMPLETED and self.statut == StatutTransaction.ANNULE:
                try:
                    caisse = self.agent.caisse
                    if self.type_operation == TypeOperation.TRANSFERT:
                        caisse.solde -= self.montant
                    elif self.type_operation == TypeOperation.RETRAIT:
                        caisse.solde += self.montant
                    caisse.save()
                except Caisse.DoesNotExist:
                    pass  # Agent has no caisse, skip balance adjustment
        super().save(*args, **kwargs)

class Depense(models.Model):
    date = models.DateField(auto_now_add=True, verbose_name=_("Date"))
    montant = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Montant"))
    devise = models.ForeignKey(Devise, on_delete=models.RESTRICT, verbose_name=_("Devise"))
    motif = models.CharField(max_length=255, verbose_name=_("Motif"))
    categorie = models.CharField(max_length=100, verbose_name=_("Catégorie"))
    destination = models.CharField(max_length=100, blank=True, verbose_name=_("Destination"))
    commentaire = models.TextField(blank=True, verbose_name=_("Commentaire"))
    justificatif = models.FileField(upload_to='depenses/', blank=True, null=True, verbose_name=_("Justificatif (PDF/Image)"))
    enregistre_par = models.ForeignKey(CustomUser, on_delete=models.RESTRICT, verbose_name=_("Enregistré par (Admin)"))

    class Meta:
        verbose_name = _("Dépense")
        verbose_name_plural = _("Dépenses")
        ordering = ['-date']

    def __str__(self):
        return f"{self.motif} - {self.montant} {self.devise.code}"

class TypeContrat(models.TextChoices):
    ASSOCIE = 'ASSOCIE', _('Associé')
    INVESTISSEUR = 'INVESTISSEUR', _('Investisseur')

class ContratPartenaire(models.Model):
    partenaire = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contrats', 
                                   limit_choices_to={'role__in': [Role.ASSOCIE, Role.INVESTISSEUR]}, verbose_name=_("Partenaire"))
    type_contrat = models.CharField(max_length=20, choices=TypeContrat.choices, verbose_name=_("Type de contrat"))
    date_debut = models.DateField(verbose_name=_("Date de début"))
    duree_mois = models.IntegerField(null=True, blank=True, verbose_name=_("Durée (mois)"), help_text="Surtout pour les investisseurs")
    montant_engage = models.DecimalField(max_digits=15, decimal_places=2, verbose_name=_("Montant engagé / investi"))
    devise = models.ForeignKey(Devise, on_delete=models.RESTRICT, verbose_name=_("Devise"))
    retour_attendu = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name=_("Retour attendu (fixes ou %)"))
    montant_paye = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name=_("Montant déjà payé"))
    statut = models.CharField(max_length=20, default="ACTIF", verbose_name=_("Statut"))

    class Meta:
        verbose_name = _("Contrat Partenaire")
        verbose_name_plural = _("Contrats Partenaires")

    def __str__(self):
        return f"Contrat de {self.partenaire.username} - {self.montant_engage} {self.devise.code}"

class PaiementPartenaire(models.Model):
    contrat = models.ForeignKey(ContratPartenaire, on_delete=models.CASCADE, related_name='paiements', verbose_name=_("Contrat"))
    date = models.DateField(auto_now_add=True, verbose_name=_("Date de paiement"))
    montant = models.DecimalField(max_digits=15, decimal_places=2, verbose_name=_("Montant payé"))
    observation = models.TextField(blank=True, verbose_name=_("Observation"))

    class Meta:
        verbose_name = _("Paiement Partenaire")
        verbose_name_plural = _("Paiements Partenaires")

    def __str__(self):
        return f"Paiement {self.montant} le {self.date} pour {self.contrat.partenaire.username}"

class StatutSession(models.TextChoices):
    OUVERT = 'OUVERT', _('Ouvert')
    FERME = 'FERMÉ', _('Fermé')

class SessionCaisse(models.Model):
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='sessions', verbose_name=_("Caisse"))
    agent = models.ForeignKey(CustomUser, on_delete=models.RESTRICT, related_name='sessions_caisse', limit_choices_to={'role__in': [Role.AGENT, Role.ADMIN]}, verbose_name=_("Agent"))
    date_ouverture = models.DateTimeField(auto_now_add=True, verbose_name=_("Heure d'ouverture"))
    date_fermeture = models.DateTimeField(null=True, blank=True, verbose_name=_("Heure de fermeture"))
    
    solde_initial = models.DecimalField(max_digits=15, decimal_places=2, verbose_name=_("Solde initial"))
    solde_final_theorique = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name=_("Solde final attendu"))
    cash_declare = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name=_("Cash déclaré (Physique)"))
    ecart = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name=_("Écart de caisse"))
    
    statut = models.CharField(max_length=20, choices=StatutSession.choices, default=StatutSession.OUVERT, verbose_name=_("Statut"))

    class Meta:
        verbose_name = _("Session de Caisse")
        verbose_name_plural = _("Sessions de Caisse")
        ordering = ['-date_ouverture']

    def __str__(self):
        return f"Session de {self.agent.username} ({self.date_ouverture.strftime('%Y-%m-%d')})"

class Commission(models.Model):
    """Track commission payments for agents"""
    agent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='commissions',
                            limit_choices_to={'role__in': [Role.AGENT]}, verbose_name=_("Agent"))
    transaction = models.ForeignKey(Transaction, on_delete=models.RESTRICT, related_name='commissions',
                                   verbose_name=_("Transaction"))
    montant_commission = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Montant commission"))
    pourcentage = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_("Pourcentage appliqué"))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_("Date de calcul"))
    statut_paiement = models.CharField(max_length=20, default='IMPAYEE', 
                                       choices=[('IMPAYEE', _('Non payée')), ('PAYEE', _('Payée'))],
                                       verbose_name=_("Statut de paiement"))
    date_paiement = models.DateTimeField(null=True, blank=True, verbose_name=_("Date de paiement"))
    
    class Meta:
        verbose_name = _("Commission")
        verbose_name_plural = _("Commissions")
        ordering = ['-date']
    
    def __str__(self):
        return f"Commission {self.montant_commission} pour {self.agent.username}"


class AgentActivityLog(models.Model):
    """Track all agent actions for audit purposes"""
    ACTION_CHOICES = [
        ('TRANSACTION_CREATE', _('Transaction créée')),
        ('TRANSACTION_CANCEL', _('Transaction annulée')),
        ('SESSION_OPEN', _('Session ouverte')),
        ('SESSION_CLOSE', _('Session fermée')),
        ('LOGIN', _('Connexion')),
        ('LOGOUT', _('Déconnexion')),
    ]
    
    agent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activity_logs',
                             limit_choices_to={'role__in': [Role.AGENT]}, verbose_name=_("Agent"))
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name=_("Action"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Date/Heure"))
    ip_address = models.CharField(max_length=45, blank=True, verbose_name=_("Adresse IP"))
    user_agent = models.TextField(blank=True, verbose_name=_("User Agent"))
    
    class Meta:
        verbose_name = _("Journal d'activité agent")
        verbose_name_plural = _("Journaux d'activité agents")
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.agent.username} - {self.get_action_display()} ({self.timestamp})"


class AgentPerformanceMetrics(models.Model):
    """Daily performance metrics for agents"""
    agent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='performance_metrics',
                             limit_choices_to={'role__in': [Role.AGENT]}, verbose_name=_("Agent"))
    date = models.DateField(verbose_name=_("Date"))
    
    # Transaction metrics
    total_transactions = models.IntegerField(default=0, verbose_name=_("Nombre transactions"))
    total_transfers = models.IntegerField(default=0, verbose_name=_("Transferts"))
    total_withdrawals = models.IntegerField(default=0, verbose_name=_("Retraits"))
    
    # Financial metrics
    total_volume = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, 
                                       verbose_name=_("Volume total (USD)"))
    total_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,
                                    verbose_name=_("Frais totaux (USD)"))
    total_commissions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,
                                           verbose_name=_("Commissions (USD)"))
    
    # Performance indicators
    average_transaction = models.DecimalField(max_digits=15, decimal_places=2, default=0.00,
                                             verbose_name=_("Montant moyen transaction (USD)"))
    
    class Meta:
        verbose_name = _("Métriques performances agent")
        verbose_name_plural = _("Métriques performances agents")
        unique_together = ('agent', 'date')
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.agent.username} - {self.date}"

class Notification(models.Model):

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications', verbose_name=_("Utilisateur"))
    message = models.CharField(max_length=255, verbose_name=_("Message"))
    is_read = models.BooleanField(default=False, verbose_name=_("Lue"))
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_("Date"))

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-date_creation']

    def __str__(self):
        return self.message


class SystemSettings(models.Model):
    """Global system configuration settings for administrators"""
    company_name = models.CharField(max_length=255, default="Rapid Cash", verbose_name=_("Nom de l'entreprise"))
    company_phone = models.CharField(max_length=20, blank=True, verbose_name=_("Téléphone de l'entreprise"))
    company_email = models.EmailField(blank=True, verbose_name=_("Email de l'entreprise"))
    company_address = models.TextField(blank=True, verbose_name=_("Adresse de l'entreprise"))
    
    # Default settings
    default_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, 
                                                       verbose_name=_("Commission par défaut (%)"))
    transaction_number_prefix = models.CharField(max_length=10, default="TX", verbose_name=_("Préfixe numéro transaction"))
    
    # Feature flags
    enable_email_notifications = models.BooleanField(default=False, verbose_name=_("Activer notifications email"))
    enable_sms_notifications = models.BooleanField(default=False, verbose_name=_("Activer notifications SMS"))
    enable_api = models.BooleanField(default=False, verbose_name=_("Activer API REST"))
    
    # Maintenance
    is_maintenance_mode = models.BooleanField(default=False, verbose_name=_("Mode maintenance"))
    maintenance_message = models.TextField(blank=True, verbose_name=_("Message maintenance"))
    
    # Audit and compliance
    enable_audit_trail = models.BooleanField(default=True, verbose_name=_("Enregistrer les audits"))
    audit_retention_days = models.IntegerField(default=365, verbose_name=_("Jours rétention audits"))
    
    # Cash management
    auto_reconcile_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, 
                                                  verbose_name=_("Seuil auto-réconciliation (USD)"))
    require_manager_approval = models.BooleanField(default=False, verbose_name=_("Approbation manager requise"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Modifié le"))
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                  related_name='settings_updates', verbose_name=_("Modifié par"))
    
    class Meta:
        verbose_name = _("Paramètres Système")
        verbose_name_plural = _("Paramètres Système")
    
    def __str__(self):
        return f"Paramètres Système - {self.updated_at.strftime('%d/%m/%Y')}"
    
    @classmethod
    def get_settings(cls):
        """Get or create default settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class TransactionAudit(models.Model):
    """Immutable audit trail for all transaction changes"""
    ACTIONS = [
        ('CREATE', _('Création')),
        ('EDIT', _('Modification')),
        ('CANCEL', _('Annulation')),
        ('VERIFY', _('Vérification')),
        ('APPROVE', _('Approbation')),
    ]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='audits', 
                                   verbose_name=_("Transaction"))
    action = models.CharField(max_length=20, choices=ACTIONS, verbose_name=_("Action"))
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                   verbose_name=_("Effectué par"))
    
    # Record previous values for edits
    old_values = models.JSONField(default=dict, blank=True, verbose_name=_("Anciennes valeurs"))
    new_values = models.JSONField(default=dict, blank=True, verbose_name=_("Nouvelles valeurs"))
    
    reason = models.TextField(blank=True, verbose_name=_("Raison"))
    ip_address = models.CharField(max_length=45, blank=True, verbose_name=_("Adresse IP"))
    user_agent = models.TextField(blank=True, verbose_name=_("User Agent"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    
    class Meta:
        verbose_name = _("Audit Transaction")
        verbose_name_plural = _("Audits Transaction")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction.numero_transaction} - {self.get_action_display()} par {self.performed_by.username}"


class APIToken(models.Model):
    """API tokens for external integrations"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='api_token', 
                               verbose_name=_("Utilisateur"))
    token = models.CharField(max_length=255, unique=True, verbose_name=_("Token"))
    
    is_active = models.BooleanField(default=True, verbose_name=_("Actif"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    last_used = models.DateTimeField(null=True, blank=True, verbose_name=_("Dernière utilisation"))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Expire le"))
    
    # Permissions
    can_view_transactions = models.BooleanField(default=True, verbose_name=_("Voir transactions"))
    can_create_transactions = models.BooleanField(default=False, verbose_name=_("Créer transactions"))
    can_view_reports = models.BooleanField(default=True, verbose_name=_("Voir rapports"))
    can_manage_users = models.BooleanField(default=False, verbose_name=_("Gérer utilisateurs"))
    
    class Meta:
        verbose_name = _("Token API")
        verbose_name_plural = _("Tokens API")
    
    def __str__(self):
        return f"Token API - {self.user.username}"
    
    def is_expired(self):
        """Check if token is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
