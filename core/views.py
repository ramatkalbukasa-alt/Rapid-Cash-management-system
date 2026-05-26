from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, FormView, View
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.db.models import Sum, Count, functions
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.forms import modelformset_factory
import json
from .models import (
    Role, Caisse, Transaction, Devise, ZoneTarif, Tarif, Depense, CustomUser, 
    Notification, TypeOperation, StatutTransaction, SessionCaisse, StatutSession,
    Commission, AgentActivityLog, AgentPerformanceMetrics, ContratPartenaire, PaiementPartenaire,
    SystemSettings, TransactionAudit, APIToken
)
from decimal import Decimal, InvalidOperation
import uuid
import logging

logger = logging.getLogger(__name__)


def get_api_token_from_request(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = None
    if auth_header.startswith('Token '):
        token_key = auth_header.split(' ', 1)[1].strip()
    else:
        token_key = request.GET.get('api_token') or request.POST.get('api_token')

    if not token_key:
        return None

    try:
        token = APIToken.objects.select_related('user').get(token=token_key, is_active=True)
        if token.is_expired():
            return None
        return token
    except APIToken.DoesNotExist:
        return None


def api_error(message, status=400):
    return JsonResponse({'detail': message}, status=status)


def transaction_to_dict(transaction):
    return {
        'id': transaction.id,
        'numero_transaction': transaction.numero_transaction,
        'date': transaction.date.isoformat(),
        'agent': {
            'id': transaction.agent.id,
            'username': transaction.agent.username,
            'role': transaction.agent.role,
        },
        'type_operation': transaction.type_operation,
        'type_operation_display': transaction.get_type_operation_display(),
        'montant': str(transaction.montant),
        'devise': transaction.devise_origine.code,
        'taux_conversion': str(transaction.taux_conversion),
        'frais_calcules': str(transaction.frais_calcules),
        'montant_reference': str(transaction.montant_reference),
        'frais_reference': str(transaction.frais_reference),
        'observation': transaction.observation,
        'statut': transaction.statut,
        'statut_display': transaction.get_statut_display(),
        'motif_annulation': transaction.motif_annulation,
    }


@method_decorator(csrf_exempt, name='dispatch')
class BaseApiView(View):
    def dispatch(self, request, *args, **kwargs):
        settings = SystemSettings.get_settings()
        if not settings.enable_api:
            return api_error('API access is disabled by system settings.', status=403)

        token = get_api_token_from_request(request)
        if token is None:
            return api_error('Authentication credentials were not provided or invalid.', status=401)

        request.api_token = token
        request.api_user = token.user
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])
        return super().dispatch(request, *args, **kwargs)


class TransactionListCreateAPIView(BaseApiView):
    def get(self, request):
        if not request.api_token.can_view_transactions:
            return api_error('Permission denied for viewing transactions.', status=403)

        queryset = Transaction.objects.all().select_related('agent', 'devise_origine')
        form = TransactionSearchForm(request.GET)
        if form.is_valid():
            if form.cleaned_data.get('numero_transaction'):
                queryset = queryset.filter(numero_transaction__icontains=form.cleaned_data['numero_transaction'])
            if form.cleaned_data.get('agent'):
                queryset = queryset.filter(agent=form.cleaned_data['agent'])
            if form.cleaned_data.get('type_operation'):
                queryset = queryset.filter(type_operation=form.cleaned_data['type_operation'])
            if form.cleaned_data.get('statut'):
                queryset = queryset.filter(statut=form.cleaned_data['statut'])
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(
                    date__gte=timezone.make_aware(
                        timezone.datetime.combine(form.cleaned_data['date_from'], timezone.datetime.min.time())
                    )
                )
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(
                    date__lte=timezone.make_aware(
                        timezone.datetime.combine(form.cleaned_data['date_to'], timezone.datetime.max.time())
                    )
                )
            if form.cleaned_data.get('montant_min'):
                queryset = queryset.filter(montant__gte=form.cleaned_data['montant_min'])
            if form.cleaned_data.get('montant_max'):
                queryset = queryset.filter(montant__lte=form.cleaned_data['montant_max'])

        transactions = [transaction_to_dict(tx) for tx in queryset.order_by('-date')]
        return JsonResponse({'count': len(transactions), 'results': transactions})

    def post(self, request):
        if not request.api_token.can_create_transactions:
            return api_error('Permission denied for creating transactions.', status=403)

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return api_error('Request body must be valid JSON.', status=400)

        required = ['agent_id', 'type_operation', 'montant', 'zone_id']
        missing = [field for field in required if not payload.get(field)]
        if missing:
            return api_error(f'Missing required fields: {", ".join(missing)}.', status=400)

        try:
            montant = Decimal(str(payload['montant']))
        except (InvalidOperation, ValueError):
            return api_error('Montant invalide.', status=400)

        if montant <= 0:
            return api_error('Le montant doit être supérieur à zéro.', status=400)

        agent = get_object_or_404(CustomUser, pk=payload['agent_id'], role__in=[Role.AGENT, Role.ADMIN])
        try:
            caisse = agent.caisse
        except Caisse.DoesNotExist:
            return api_error('L’agent n’a pas de caisse associée.', status=400)

        zone = get_object_or_404(ZoneTarif, pk=payload['zone_id'])
        tarif = Tarif.objects.filter(zone_id=payload['zone_id'], montant_min__lte=montant, montant_max__gte=montant).first()
        frais = tarif.frais_fixe if tarif else Decimal('0.00')
        montant_usd = montant * caisse.devise.taux_reference_usd
        frais_usd = frais * caisse.devise.taux_reference_usd

        if payload['type_operation'] == TypeOperation.RETRAIT and caisse.solde < montant:
            return api_error('Fonds insuffisants dans la caisse pour ce retrait.', status=400)

        numero = uuid.uuid4().hex[:8].upper()
        transaction = Transaction.objects.create(
            numero_transaction=numero,
            agent=agent,
            type_operation=payload['type_operation'],
            montant=montant,
            devise_origine=caisse.devise,
            taux_conversion=Decimal('1.0000'),
            frais_calcules=frais,
            montant_reference=montant_usd,
            frais_reference=frais_usd,
            observation=payload.get('observation', f"Vers {zone.nom}"),
        )

        if payload['type_operation'] == TypeOperation.TRANSFERT:
            caisse.solde += montant
        else:
            caisse.solde -= montant
        caisse.save()

        session = SessionCaisse.objects.filter(agent=agent, statut=StatutSession.OUVERT).first()
        if session:
            session.solde_final_theorique = caisse.solde
            session.save()

        return JsonResponse({'detail': 'Transaction créée.', 'transaction': transaction_to_dict(transaction)}, status=201)


class TransactionDetailAPIView(BaseApiView):
    def get(self, request, transaction_id):
        if not request.api_token.can_view_transactions:
            return api_error('Permission denied for viewing transaction details.', status=403)

        transaction = get_object_or_404(Transaction, id=transaction_id)
        return JsonResponse(transaction_to_dict(transaction))


class SystemSettingsAPIView(BaseApiView):
    def get(self, request):
        if not request.api_token.can_view_reports:
            return api_error('Permission denied for viewing system settings.', status=403)

        settings = SystemSettings.get_settings()
        return JsonResponse({
            'company_name': settings.company_name,
            'phone_number': settings.phone_number,
            'email_address': settings.email_address,
            'physical_address': settings.physical_address,
            'default_commission_percentage': str(settings.default_commission_percentage),
            'transaction_number_prefix': settings.transaction_number_prefix,
            'enable_email_notifications': settings.enable_email_notifications,
            'enable_sms_notifications': settings.enable_sms_notifications,
            'enable_api': settings.enable_api,
            'is_maintenance_mode': settings.is_maintenance_mode,
            'enable_two_factor_auth': settings.enable_two_factor_auth,
            'auto_reconcile_enabled': settings.auto_reconcile_enabled,
            'auto_reconcile_threshold': str(settings.auto_reconcile_threshold),
            'audit_log_retention_days': settings.audit_log_retention_days,
        })


def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect('two_factor:login')
    
    role = request.user.role
    if role == Role.ADMIN:
        return redirect('core:admin_dashboard')
    elif role == Role.AGENT:
        return redirect('core:agent_dashboard')
    elif role == Role.ASSOCIE:
        return redirect('core:associe_dashboard')
    elif role == Role.INVESTISSEUR:
        return redirect('core:investisseur_dashboard')
    else:
        return redirect('two_factor:login')

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == Role.ADMIN

class AgentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == Role.AGENT

class AssocieRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == Role.ASSOCIE

class InvestisseurRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == Role.INVESTISSEUR

from .forms import DepenseForm, CaisseAdjustmentForm, CustomUserCreationAdminForm, CustomUserChangeAdminForm, UserProfileForm, CloseSessionForm, SystemSettingsForm, TransactionEditForm, TransactionSearchForm


class ManageUsersView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'core/manage_users.html'
    context_object_name = 'users'
    ordering = ['-date_joined']

class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationAdminForm
    template_name = 'core/user_form.html'
    success_url = reverse_lazy('core:manage_users')
    success_message = "Utilisateur créé avec succès ! Le mot de passe par défaut a été appliqué ou choisi lors de la création."

class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeAdminForm
    template_name = 'core/user_form.html'
    success_url = reverse_lazy('core:manage_users')
    success_message = "Utilisateur mis à jour avec succès"

class UserDeactivateView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        user.is_active = not user.is_active
        user.save()
        status = "activé" if user.is_active else "désactivé"
        messages.success(request, f"Compte de {user.username} {status} avec succès.")
        return redirect('core:manage_users')

class UserPasswordResetView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        new_password = "Password123!"
        user.set_password(new_password)
        user.save()
        messages.success(request, f"Mot de passe de {user.username} réinitialisé avec succès.")
        return redirect('core:manage_users')

class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'core/admin_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fix #2 — Only count COMPLETED transactions
        completed_txs = Transaction.objects.filter(statut=StatutTransaction.COMPLETED)
        
        # Fix #4 — Clearly named as global, not daily
        volume_global = completed_txs.aggregate(total=Sum('montant_reference'))['total'] or Decimal('0.00')
        frais = completed_txs.aggregate(total=Sum('frais_reference'))['total'] or Decimal('0.00')

        # Fix #1 — Convert each depense to USD before summing
        toutes_depenses = Depense.objects.select_related('devise').all()
        depenses_usd = sum(
            (dep.montant * dep.devise.taux_reference_usd for dep in toutes_depenses),
            Decimal('0.00')
        )

        # Fix #5 — Commissions only on TRANSFERT, exclude RETRAIT
        commissions = Decimal('0.00')
        agents = CustomUser.objects.filter(role=Role.AGENT)
        for agent in agents:
            agent_txs = completed_txs.filter(agent=agent, type_operation=TypeOperation.TRANSFERT)
            frais_agent = agent_txs.aggregate(total=Sum('frais_reference'))['total'] or Decimal('0.00')
            try:
                pct = agent.agent_profile.commission_pourcentage
                commissions += (frais_agent * pct / 100)
            except AttributeError:
                pass
            
        context['volume_global'] = volume_global
        context['frais_collectes'] = frais
        context['depenses_total'] = depenses_usd
        context['commissions_total'] = commissions
        context['benefice_net'] = frais - depenses_usd - commissions
        context['recent_transactions'] = Transaction.objects.all().order_by('-date')[:5]

        # Additional KPI metrics
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        context['transactions_today'] = completed_txs.filter(date__gte=today_start).aggregate(total=Sum('montant_reference'))['total'] or Decimal('0.00')
        context['transactions_month'] = completed_txs.filter(date__gte=month_start).aggregate(total=Sum('montant_reference'))['total'] or Decimal('0.00')
        context['total_transactions'] = completed_txs.count()
        context['total_transferts'] = completed_txs.filter(type_operation=TypeOperation.TRANSFERT).count()
        context['total_retraits'] = completed_txs.filter(type_operation=TypeOperation.RETRAIT).count()
        context['average_transaction'] = (volume_global / context['total_transactions']) if context['total_transactions'] else Decimal('0.00')
        context['open_sessions_count'] = SessionCaisse.objects.filter(statut=StatutSession.OUVERT).count()
        context['active_agents_count'] = CustomUser.objects.filter(role=Role.AGENT, is_active=True).count()
        context['pending_transactions'] = Transaction.objects.exclude(statut=StatutTransaction.COMPLETED).count()

        # Chart Data: Last 7 days volume (COMPLETED only — already correct)
        last_7_days = timezone.now() - timezone.timedelta(days=7)
        daily_stats = completed_txs.filter(date__gte=last_7_days)\
            .annotate(day=functions.TruncDate('date'))\
            .values('day')\
            .annotate(total=Sum('montant_reference'))\
            .order_by('day')
        
        context['chart_labels'] = [s['day'].strftime('%d/%m') for s in daily_stats]
        context['chart_data'] = [float(s['total']) for s in daily_stats]
        
        # Operation context for admin if they have a caisse
        try:
            caisse = self.request.user.caisse
            context['caisse'] = caisse
            context['session_ouverte'] = SessionCaisse.objects.filter(
                agent=self.request.user, 
                statut=StatutSession.OUVERT
            ).first()
        except Caisse.DoesNotExist:
            context['caisse'] = None
            context['session_ouverte'] = None
            
        context['my_recent_transactions'] = Transaction.objects.filter(agent=self.request.user).order_by('-date')[:5]
        context['devises'] = Devise.objects.all()
        context['zones'] = ZoneTarif.objects.all()
        
        return context

class ManageReportsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'core/manage_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        
        completed_txs = Transaction.objects.filter(statut=StatutTransaction.COMPLETED)
        context['volume_global'] = completed_txs.aggregate(total=Sum('montant_reference'))['total'] or Decimal('0.00')
        context['frais_global'] = completed_txs.aggregate(total=Sum('frais_reference'))['total'] or Decimal('0.00')
        context['tx_count'] = completed_txs.count()
        context['current_quarter'] = (now.month - 1) // 3 + 1
        context['current_year'] = now.year
        return context

class ManageExpensesView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'core/manage_expenses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenses'] = Depense.objects.all().order_by('-date')
        context['form'] = DepenseForm()
        return context

    def post(self, request, *args, **kwargs):
        form = DepenseForm(request.POST, request.FILES)
        if form.is_valid():
            depense = form.save(commit=False)
            depense.enregistre_par = request.user
            depense.save()
            return redirect('core:manage_expenses')
        return self.get(request, *args, **kwargs)

class ManageCaissesView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'core/manage_caisses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['caisses'] = Caisse.objects.all()
        context['form'] = CaisseAdjustmentForm()
        return context

    def post(self, request, *args, **kwargs):
        form = CaisseAdjustmentForm(request.POST)
        if form.is_valid():
            agent = form.cleaned_data['agent']
            montant = form.cleaned_data['montant']
            type_adj = form.cleaned_data['type_ajustement']
            
            # Check if agent has a caisse
            try:
                caisse = agent.caisse
            except Caisse.DoesNotExist:
                form.add_error('agent', f"L'agent {agent.username} n'a pas de caisse associée.")
                return self.get(request, *args, **kwargs)
            
            # Simplistic adjustment
            if type_adj == 'ALLOCATION':
                caisse.solde += montant
            else: # DEDUCTION
                caisse.solde -= montant
            caisse.save()
            return redirect('core:manage_caisses')
        return self.get(request, *args, **kwargs)

class AgentDashboardView(LoginRequiredMixin, AgentRequiredMixin, TemplateView):
    template_name = 'core/agent_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            caisse = self.request.user.caisse
            context['caisse'] = caisse
            context['session_ouverte'] = SessionCaisse.objects.filter(
                agent=self.request.user, 
                statut=StatutSession.OUVERT
            ).first()
        except Caisse.DoesNotExist:
            context['caisse'] = None
            context['session_ouverte'] = None
        
        context['recent_transactions'] = Transaction.objects.filter(agent=self.request.user).order_by('-date')[:5]
        context['devises'] = Devise.objects.all()
        context['zones'] = ZoneTarif.objects.all()
        return context

class AssocieDashboardView(LoginRequiredMixin, AssocieRequiredMixin, TemplateView):
    template_name = 'core/associe_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_partner_balance
        from .models import ContratPartenaire, PaiementPartenaire, RapportMensuelAssocie
        
        balance_info = get_partner_balance(self.request.user)
        context.update(balance_info)
        
        # Get all contracts with payment info
        contracts = ContratPartenaire.objects.filter(partenaire=self.request.user)
        contracts_detail = []
        for contract in contracts:
            last_payment = PaiementPartenaire.objects.filter(contrat=contract).order_by('-date').first()
            contracts_detail.append({
                'contract': contract,
                'last_payment': last_payment,
                'remaining': contract.montant_engage - contract.montant_paye,
                'pct_complete': (contract.montant_paye / contract.montant_engage * 100) if contract.montant_engage > 0 else 0,
            })
        
        context['contracts'] = contracts_detail
        
        # === OPERATION CAPABILITIES (same as Agent) ===
        try:
            caisse = self.request.user.caisse
            context['caisse'] = caisse
            context['session_ouverte'] = SessionCaisse.objects.filter(
                agent=self.request.user, 
                statut=StatutSession.OUVERT
            ).first()
        except Caisse.DoesNotExist:
            context['caisse'] = None
            context['session_ouverte'] = None
        
        context['recent_transactions'] = Transaction.objects.filter(agent=self.request.user).order_by('-date')[:10]
        context['devises'] = Devise.objects.all()
        context['zones'] = ZoneTarif.objects.all()
        
        # === MONTHLY REPORTS ===
        rapports = RapportMensuelAssocie.objects.filter(
            contrat__partenaire=self.request.user
        ).order_by('-annee', '-mois')[:12]
        context['rapports_mensuels'] = rapports
        
        # Current month stats
        now = timezone.now()
        current_month_txs = Transaction.objects.filter(
            agent=self.request.user,
            statut=StatutTransaction.COMPLETED,
            date__month=now.month,
            date__year=now.year
        )
        context['ops_mois_count'] = current_month_txs.count()
        context['ops_mois_volume'] = current_month_txs.aggregate(
            total=Sum('montant_reference'))['total'] or Decimal('0.00')
        context['ops_mois_frais'] = current_month_txs.aggregate(
            total=Sum('frais_reference'))['total'] or Decimal('0.00')
        
        return context

class InvestisseurDashboardView(LoginRequiredMixin, InvestisseurRequiredMixin, TemplateView):
    template_name = 'core/investisseur_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_partner_balance
        from .models import ContratPartenaire, PaiementPartenaire, GainMensuelInvestisseur
        
        balance_info = get_partner_balance(self.request.user)
        context.update(balance_info)
        
        # Get all contracts with payment info
        contracts = ContratPartenaire.objects.filter(partenaire=self.request.user)
        contracts_detail = []
        for contract in contracts:
            last_payment = PaiementPartenaire.objects.filter(contrat=contract).order_by('-date').first()
            contracts_detail.append({
                'contract': contract,
                'last_payment': last_payment,
                'remaining': contract.montant_engage - contract.montant_paye,
                'pct_complete': (contract.montant_paye / contract.montant_engage * 100) if contract.montant_engage > 0 else 0,
            })
        
        context['contracts'] = contracts_detail
        
        # === MONTHLY GAINS HISTORY ===
        gains = GainMensuelInvestisseur.objects.filter(
            contrat__partenaire=self.request.user
        ).order_by('-annee', '-mois')[:12]
        context['gains_mensuels'] = gains
        
        # Total gains received
        from django.db.models import Sum
        total_gains = GainMensuelInvestisseur.objects.filter(
            contrat__partenaire=self.request.user,
            statut='PAYE'
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
        context['total_gains_recus'] = total_gains
        
        # Pending gains
        pending_gains = GainMensuelInvestisseur.objects.filter(
            contrat__partenaire=self.request.user,
            statut='EN_ATTENTE'
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
        context['gains_en_attente'] = pending_gains
        
        return context

# HTMX View
def calculate_fee(request):
    montant = request.GET.get('montant', 0)
    zone_id = request.GET.get('zone', None)
    
    try:
        if not montant or not zone_id:
            fee = Decimal('0.00')
        else:
            montant = Decimal(montant)
            tarif = Tarif.objects.filter(zone_id=zone_id, montant_min__lte=montant, montant_max__gte=montant).first()
            fee = tarif.frais_fixe if tarif else Decimal('0.00')
    except (ValueError, TypeError, InvalidOperation):
        fee = Decimal('0.00')
        
    return HttpResponse(f'<h2 id="fee-display" style="color: var(--primary); margin: 0;">{fee} $</h2>')

def process_transaction(request):
    if request.method == 'POST':
        montant_str = request.POST.get('montant', '0')
        zone_id = request.POST.get('zone')
        type_op = request.POST.get('type') # Corrected from type_operation
        
        def _get_redirect(user):
            if user.role == Role.ADMIN:
                return redirect('core:admin_dashboard')
            elif user.role == Role.ASSOCIE:
                return redirect('core:associe_dashboard')
            return redirect('core:agent_dashboard')
        
        try:
            montant = Decimal(montant_str)
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant invalide.")
            return _get_redirect(request.user)

        if montant <= 0:
            messages.error(request, "Le montant doit être supérieur à zéro.")
            return _get_redirect(request.user)
            
        session = SessionCaisse.objects.filter(agent=request.user, statut=StatutSession.OUVERT).first()
        if not session:
            messages.error(request, "Vous devez ouvrir votre caisse avant de procéder à une transaction.")
            return _get_redirect(request.user)
        
        try:
            caisse = request.user.caisse
        except Caisse.DoesNotExist:
            messages.error(request, "Aucune caisse n'est associée à votre compte. Contactez l'administrateur.")
            return _get_redirect(request.user)

        devise = caisse.devise
        zone = get_object_or_404(ZoneTarif, id=zone_id)

        tarif = Tarif.objects.filter(zone_id=zone_id, montant_min__lte=montant, montant_max__gte=montant).first()
        frais = tarif.frais_fixe if tarif else Decimal('0.00')
        
        montant_usd = montant * devise.taux_reference_usd
        frais_usd = frais * devise.taux_reference_usd

        if type_op == TypeOperation.RETRAIT and caisse.solde < montant:
            messages.error(request, "Fonds insuffisants dans la caisse pour ce retrait.")
            return _get_redirect(request.user)
        
        numero = uuid.uuid4().hex[:8].upper()
        transaction = Transaction.objects.create(
            numero_transaction=numero,
            agent=request.user,
            type_operation=type_op,
            montant=montant,
            devise_origine=caisse.devise,
            taux_conversion=1.0000,
            frais_calcules=frais,
            montant_reference=montant_usd,
            frais_reference=frais_usd,
            observation=f"Vers {zone.nom}"
        )
        
        # Update caisse
        if type_op == TypeOperation.TRANSFERT: # client sends money, agent gets it -> caisse goes up
            caisse.solde += montant
        else: # RETRAIT: client withdraws money, agent pays out -> caisse goes down
            caisse.solde -= montant
        caisse.save()
        
        # Log to the active session
        session.solde_final_theorique = caisse.solde
        session.save()

        messages.success(request, f"Transaction {type_op} de {montant} {caisse.devise.code} réussie. Frais: {frais}.")
        
        # Notify admins
        admins = CustomUser.objects.filter(role=Role.ADMIN)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                message=f"Nouvelle opération: {type_op} de {montant} {devise.code} par {request.user.username}"
            )
        
        if request.user.role == Role.ADMIN:
            return redirect('core:admin_dashboard')
        elif request.user.role == Role.ASSOCIE:
            return redirect('core:associe_dashboard')
        return redirect('core:agent_dashboard')

class OpenSessionView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role not in [Role.AGENT, Role.ADMIN, Role.ASSOCIE]:
            messages.error(request, "Accès non autorisé.")
            return redirect('/')
        try:
            caisse = request.user.caisse
        except Exception:
            messages.error(request, "Aucune caisse associée à votre compte. Contactez l'administrateur.")
            return self._redirect(request)
        if SessionCaisse.objects.filter(agent=request.user, statut=StatutSession.OUVERT).exists():
            messages.warning(request, "Une session est déjà ouverte.")
            return self._redirect(request)
        SessionCaisse.objects.create(
            caisse=caisse,
            agent=request.user,
            solde_initial=caisse.solde,
            solde_final_theorique=caisse.solde
        )
        messages.success(request, "Caisse ouverte avec succès. Bon service !")
        return self._redirect(request)
    
    def _redirect(self, request):
        if request.user.role == Role.ADMIN:
            return redirect('core:admin_dashboard')
        elif request.user.role == Role.ASSOCIE:
            return redirect('core:associe_dashboard')
        return redirect('core:agent_dashboard')

class CloseSessionView(LoginRequiredMixin, FormView):
    template_name = 'core/close_session.html'
    form_class = CloseSessionForm
    success_url = reverse_lazy('core:agent_dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in [Role.AGENT, Role.ADMIN, Role.ASSOCIE]:
            messages.error(request, "Accès non autorisé.")
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = SessionCaisse.objects.filter(agent=self.request.user, statut=StatutSession.OUVERT).first()
        context['caisse_session'] = session
        return context

    def form_valid(self, form):
        session = SessionCaisse.objects.filter(agent=self.request.user, statut=StatutSession.OUVERT).first()
        if not session:
            return redirect(self.get_success_url())
            
        cash_declare = form.cleaned_data['cash_declare']
        session.cash_declare = cash_declare
        session.ecart = cash_declare - session.solde_final_theorique
        session.date_fermeture = timezone.now()
        session.statut = StatutSession.FERME
        session.save()
        
        messages.warning(request=self.request, message=f"Session clôturée. Écart: {session.ecart} $")
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.role == Role.ADMIN:
            return reverse('core:admin_dashboard')
        elif self.request.user.role == Role.ASSOCIE:
            return reverse('core:associe_dashboard')
        return reverse('core:agent_dashboard')

class ManageTauxView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'core/manage_taux.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        TauxFormSet = modelformset_factory(Devise, fields=('code', 'taux_reference_usd'), extra=0)
        devises = Devise.objects.all().order_by('id')
        formset = TauxFormSet(queryset=devises)
        context['formset'] = formset
        context['zipped_data'] = zip(formset, devises)
        return context

    def post(self, request, *args, **kwargs):
        TauxFormSet = modelformset_factory(Devise, fields=('code', 'taux_reference_usd'), extra=0)
        formset = TauxFormSet(request.POST, queryset=Devise.objects.all())
        if formset.is_valid():
            formset.save()
            messages.success(request, "Taux de change mis à jour avec succès.")
            return redirect('core:manage_taux')
        return render(request, self.template_name, {'formset': formset})

class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'core/user_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = UserProfileForm(instance=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour avec succès.")
            return redirect('core:user_profile')
        return render(request, self.template_name, {'form': form})


# ===================== NEW VIEWS FOR ENHANCED FEATURES =====================

class AgentPerformanceView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Admin view to track agent performance metrics"""
    model = CustomUser
    template_name = 'core/agent_performance.html'
    context_object_name = 'agents'
    
    def get_queryset(self):
        return CustomUser.objects.filter(role=Role.AGENT).prefetch_related('transactions', 'commissions')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_agent_performance_metrics
        
        agents_with_metrics = []
        total_fees = Decimal('0.00')
        total_commissions = Decimal('0.00')
        for agent in self.get_queryset():
            metrics = get_agent_performance_metrics(agent)
            metrics['agent'] = agent
            total_fees += metrics.get('total_fees', Decimal('0.00'))
            total_commissions += metrics.get('total_commissions', Decimal('0.00'))
            agents_with_metrics.append(metrics)
        
        context['agents_metrics'] = agents_with_metrics
        context['total_agent_fees'] = total_fees
        context['total_agent_commissions'] = total_commissions
        return context


class CommissionTrackingView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Admin view to track commissions"""
    from .models import Commission
    model = Commission
    template_name = 'core/commission_tracking.html'
    context_object_name = 'commissions'
    paginate_by = 50
    ordering = ['-date']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Summary statistics
        from .models import Commission
        all_commissions = Commission.objects.all()
        context['total_commissions'] = all_commissions.aggregate(
            total=Sum('montant_commission')
        )['total'] or Decimal('0.00')
        
        context['paid_commissions'] = all_commissions.filter(
            statut_paiement='PAYEE'
        ).aggregate(total=Sum('montant_commission'))['total'] or Decimal('0.00')
        
        context['unpaid_commissions'] = all_commissions.filter(
            statut_paiement='IMPAYEE'
        ).aggregate(total=Sum('montant_commission'))['total'] or Decimal('0.00')
        
        return context


class PartnerContractDetailView(LoginRequiredMixin, TemplateView):
    """View for partners to see contract details"""
    template_name = 'core/contract_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract_id = self.kwargs.get('contract_id')
        
        from .models import ContratPartenaire, PaiementPartenaire
        contract = get_object_or_404(ContratPartenaire, id=contract_id)
        
        # Check permission - user must own this contract
        if contract.partenaire != self.request.user and self.request.user.role != Role.ADMIN:
            return HttpResponseRedirect('/')
        
        context['contract'] = contract
        context['payments'] = PaiementPartenaire.objects.filter(contrat=contract).order_by('-date')
        
        # Calculate balance
        balance = contract.montant_engage - contract.montant_paye
        context['remaining_balance'] = balance
        context['percentage_paid'] = (contract.montant_paye / contract.montant_engage * 100) if contract.montant_engage > 0 else 0
        
        return context


class PartnerBalanceView(LoginRequiredMixin, TemplateView):
    """View for partners to see their overall financial position"""
    template_name = 'core/partner_balance.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Only partners can access this
        if request.user.role not in [Role.ASSOCIE, Role.INVESTISSEUR]:
            messages.error(request, "Accès non autorisé.")
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_partner_balance
        
        balance_info = get_partner_balance(self.request.user)
        context.update(balance_info)
        
        # Get all contracts with details
        from .models import ContratPartenaire, PaiementPartenaire
        contracts = ContratPartenaire.objects.filter(partenaire=self.request.user)
        
        contracts_with_details = []
        for contract in contracts:
            payments = PaiementPartenaire.objects.filter(contrat=contract)
            contract_detail = {
                'contract': contract,
                'total_payments': payments.count(),
                'last_payment': payments.order_by('-date').first(),
                'remaining': contract.montant_engage - contract.montant_paye,
            }
            contracts_with_details.append(contract_detail)
        
        context['contracts'] = contracts_with_details
        return context


class AuditLogView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Admin view for activity audit logs"""
    from .models import AgentActivityLog
    model = AgentActivityLog
    template_name = 'core/audit_log.html'
    context_object_name = 'logs'
    paginate_by = 100
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by agent if specified
        agent_id = self.request.GET.get('agent')
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
        
        # Filter by action if specified
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import AgentActivityLog
        
        context['agents'] = CustomUser.objects.filter(role=Role.AGENT)
        context['actions'] = AgentActivityLog.ACTION_CHOICES
        context['selected_agent'] = self.request.GET.get('agent')
        context['selected_action'] = self.request.GET.get('action')
        
        return context


class ManageCommissionsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Admin view to manage commission rates and payments"""
    template_name = 'core/manage_commissions.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all agents with their commission rates
        agents = CustomUser.objects.filter(role=Role.AGENT).select_related('agent_profile')
        
        agents_commissions = []
        for agent in agents:
            try:
                pct = agent.agent_profile.commission_pourcentage
            except:
                pct = Decimal('0.00')
            
            agents_commissions.append({
                'agent': agent,
                'commission_pct': pct,
            })
        
        context['agents_commissions'] = agents_commissions
        return context


# ===================== SYSTEM SETTINGS & ADVANCED MANAGEMENT =====================

class SystemSettingsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Admin view for system configuration"""
    template_name = 'core/system_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = SystemSettings.get_settings()
        context['form'] = SystemSettingsForm(instance=settings)
        context['settings'] = settings
        return context
    
    def post(self, request, *args, **kwargs):
        settings = SystemSettings.get_settings()
        form = SystemSettingsForm(request.POST, instance=settings)
        
        if form.is_valid():
            settings = form.save(commit=False)
            settings.updated_by = request.user
            settings.save()
            
            # Log to activity
            AgentActivityLog.objects.create(
                agent=request.user,
                action='OTHER',
                description=f"Modification des paramètres système",
                ip_address=self.get_client_ip(request)
            ) if hasattr(request.user, 'agent') else None
            
            messages.success(request, "Paramètres système mis à jour avec succès.")
            return redirect('core:system_settings')
        
        return render(request, self.template_name, {'form': form, 'settings': settings})
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TransactionManagementView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Admin view for managing transactions with advanced search and edit"""
    model = Transaction
    template_name = 'core/transaction_management.html'
    context_object_name = 'transactions'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Transaction.objects.all().select_related('agent', 'devise_origine')
        
        # Apply filters from search form
        form = TransactionSearchForm(self.request.GET)
        
        if form.is_valid():
            if form.cleaned_data.get('numero_transaction'):
                queryset = queryset.filter(
                    numero_transaction__icontains=form.cleaned_data['numero_transaction']
                )
            
            if form.cleaned_data.get('agent'):
                queryset = queryset.filter(agent=form.cleaned_data['agent'])
            
            if form.cleaned_data.get('type_operation'):
                queryset = queryset.filter(type_operation=form.cleaned_data['type_operation'])
            
            if form.cleaned_data.get('statut'):
                queryset = queryset.filter(statut=form.cleaned_data['statut'])
            
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(
                    date__gte=timezone.make_aware(
                        timezone.datetime.combine(form.cleaned_data['date_from'], timezone.datetime.min.time())
                    )
                )
            
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(
                    date__lte=timezone.make_aware(
                        timezone.datetime.combine(form.cleaned_data['date_to'], timezone.datetime.max.time())
                    )
                )
            
            if form.cleaned_data.get('montant_min'):
                queryset = queryset.filter(montant__gte=form.cleaned_data['montant_min'])
            
            if form.cleaned_data.get('montant_max'):
                queryset = queryset.filter(montant__lte=form.cleaned_data['montant_max'])
        
        return queryset.order_by('-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = TransactionSearchForm(self.request.GET)
        context['total_transactions'] = self.get_queryset().count()
        context['total_volume'] = self.get_queryset().aggregate(
            total=Sum('montant_reference')
        )['total'] or Decimal('0.00')
        return context


class TransactionEditView(LoginRequiredMixin, AdminRequiredMixin, View):
    """Allow admins to edit transaction details with audit trail"""
    template_name = 'core/transaction_edit.html'
    
    def get(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        form = TransactionEditForm(instance=transaction)
        audits = TransactionAudit.objects.filter(transaction=transaction)
        
        return render(request, self.template_name, {
            'transaction': transaction,
            'form': form,
            'audits': audits
        })
    
    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        form = TransactionEditForm(request.POST, instance=transaction)
        
        if form.is_valid():
            # Track old values for audit
            old_montant = transaction.montant
            old_frais = transaction.frais_calcules
            old_observation = transaction.observation
            old_statut = transaction.statut
            
            # Save transaction
            transaction = form.save()
            
            # Create audit record
            TransactionAudit.objects.create(
                transaction=transaction,
                action='EDIT',
                performed_by=request.user,
                old_values={
                    'montant': str(old_montant),
                    'frais_calcules': str(old_frais),
                    'observation': old_observation,
                    'statut': old_statut,
                },
                new_values={
                    'montant': str(transaction.montant),
                    'frais_calcules': str(transaction.frais_calcules),
                    'observation': transaction.observation,
                    'statut': transaction.statut,
                },
                reason=request.POST.get('edit_reason', 'Modification administrative'),
                ip_address=self.get_client_ip(request)
            )
            
            messages.success(request, "Transaction mise à jour et audit enregistré.")
            return redirect('core:transaction_management')
        
        audits = TransactionAudit.objects.filter(transaction=transaction)
        return render(request, self.template_name, {
            'transaction': transaction,
            'form': form,
            'audits': audits
        })
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ExportTransactionsCsvView(LoginRequiredMixin, AdminRequiredMixin, View):
    """Export transactions to CSV format"""
    
    def get(self, request):
        import csv
        from django.http import StreamingHttpResponse
        
        # Build filename with date
        filename = f"transactions_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        response = StreamingHttpResponse(
            self.get_csv_rows(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
        return response
    
    def get_csv_rows(self):
        """Generate CSV rows"""
        import csv
        import io
        
        # Get transactions
        form = TransactionSearchForm(self.request.GET)
        if form.is_valid():
            # Apply same filters as TransactionManagementView
            transactions = Transaction.objects.all()
            if form.cleaned_data.get('agent'):
                transactions = transactions.filter(agent=form.cleaned_data['agent'])
            # ... apply other filters similarly
        else:
            transactions = Transaction.objects.all()
        
        # Create CSV writer
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'N° Transaction', 'Date', 'Agent', 'Type', 'Montant', 'Devise',
            'Frais', 'Montant USD', 'Frais USD', 'Statut', 'Observation'
        ])
        yield output.getvalue()
        
        # Write transactions
        for transaction in transactions.order_by('-date'):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                transaction.numero_transaction,
                transaction.date.strftime('%d/%m/%Y %H:%M'),
                transaction.agent.username,
                transaction.type_operation,
                transaction.montant,
                transaction.devise_origine.code,
                transaction.frais_calcules,
                transaction.montant_reference,
                transaction.frais_reference,
                transaction.statut,
                transaction.observation
            ])
            yield output.getvalue()


def export_transactions_excel(request):
    """Export transactions to Excel format"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        messages.error(request, "Excel export nécessite openpyxl. Installer avec: pip install openpyxl")
        return redirect('core:transaction_management')
    
    if not request.user.is_superuser and request.user.role != Role.ADMIN:
        messages.error(request, "Accès non autorisé.")
        return redirect('/')
    
    from django.http import HttpResponse
    
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"
    
    # Write headers
    headers = ['N° Transaction', 'Date', 'Agent', 'Type', 'Montant', 'Devise', 
               'Frais', 'Montant USD', 'Frais USD', 'Statut', 'Observation']
    
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
    
    # Write data
    transactions = Transaction.objects.all().order_by('-date')
    for row, transaction in enumerate(transactions, 2):
        ws.cell(row=row, column=1, value=transaction.numero_transaction)
        ws.cell(row=row, column=2, value=transaction.date.strftime('%d/%m/%Y %H:%M'))
        ws.cell(row=row, column=3, value=transaction.agent.username)
        ws.cell(row=row, column=4, value=transaction.type_operation)
        ws.cell(row=row, column=5, value=float(transaction.montant))
        ws.cell(row=row, column=6, value=transaction.devise_origine.code)
        ws.cell(row=row, column=7, value=float(transaction.frais_calcules))
        ws.cell(row=row, column=8, value=float(transaction.montant_reference))
        ws.cell(row=row, column=9, value=float(transaction.frais_reference))
        ws.cell(row=row, column=10, value=transaction.statut)
        ws.cell(row=row, column=11, value=transaction.observation)
    
    # Auto-size columns
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        ws.column_dimensions[column_letter].width = max_length + 2
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="transactions_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    wb.save(response)
    
    return response


# ===================== INVESTOR & ASSOCIATE MANAGEMENT =====================

class ManageInvestorGainsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Admin view to set monthly gains for investors"""
    template_name = 'core/manage_investor_gains.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import ContratPartenaire, GainMensuelInvestisseur, TypeContrat
        
        # Active investor contracts
        investor_contracts = ContratPartenaire.objects.filter(
            type_contrat=TypeContrat.INVESTISSEUR,
            statut='ACTIF'
        ).select_related('partenaire', 'devise')
        context['investor_contracts'] = investor_contracts
        
        # Recent gains
        context['recent_gains'] = GainMensuelInvestisseur.objects.all().order_by('-annee', '-mois')[:20]
        
        return context
    
    def post(self, request, *args, **kwargs):
        from .models import ContratPartenaire, GainMensuelInvestisseur
        
        contrat_id = request.POST.get('contrat_id')
        montant = request.POST.get('montant')
        mois = request.POST.get('mois')
        annee = request.POST.get('annee')
        observation = request.POST.get('observation', '')
        
        try:
            contrat = ContratPartenaire.objects.get(id=contrat_id)
            montant = Decimal(montant)
            mois = int(mois)
            annee = int(annee)
            
            # Validate amount is within range
            if contrat.rendement_min and montant < contrat.rendement_min:
                messages.error(request, f"Le montant doit être >= {contrat.rendement_min} USD (min contractuel)")
                return redirect('core:manage_investor_gains')
            if contrat.rendement_max and montant > contrat.rendement_max:
                messages.error(request, f"Le montant doit être <= {contrat.rendement_max} USD (max contractuel)")
                return redirect('core:manage_investor_gains')
            
            # Check if gain already exists
            if GainMensuelInvestisseur.objects.filter(contrat=contrat, mois=mois, annee=annee).exists():
                messages.error(request, f"Un gain existe déjà pour ce contrat en {mois}/{annee}")
                return redirect('core:manage_investor_gains')
            
            GainMensuelInvestisseur.objects.create(
                contrat=contrat,
                mois=mois,
                annee=annee,
                montant=montant,
                attribue_par=request.user,
                observation=observation
            )
            
            messages.success(request, f"Gain de {montant} USD attribué à {contrat.partenaire.get_full_name()} pour {mois}/{annee}")
            
        except ContratPartenaire.DoesNotExist:
            messages.error(request, "Contrat introuvable.")
        except (ValueError, TypeError) as e:
            messages.error(request, f"Données invalides: {e}")
        
        return redirect('core:manage_investor_gains')


class ManageAssociateReportsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Admin view to see/manage associate monthly reports"""
    template_name = 'core/manage_associate_reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import RapportMensuelAssocie
        
        context['rapports'] = RapportMensuelAssocie.objects.all().select_related(
            'contrat', 'contrat__partenaire'
        ).order_by('-annee', '-mois')[:50]
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Mark report as paid"""
        from .models import RapportMensuelAssocie
        
        rapport_id = request.POST.get('rapport_id')
        action = request.POST.get('action')
        
        try:
            rapport = RapportMensuelAssocie.objects.get(id=rapport_id)
            if action == 'valider':
                rapport.statut = 'VALIDE'
                rapport.save()
                messages.success(request, f"Rapport {rapport.mois}/{rapport.annee} validé.")
            elif action == 'payer':
                rapport.statut = 'PAYE'
                rapport.date_paiement = timezone.now()
                rapport.save()
                messages.success(request, f"Rapport {rapport.mois}/{rapport.annee} marqué comme payé.")
        except RapportMensuelAssocie.DoesNotExist:
            messages.error(request, "Rapport introuvable.")
        
        return redirect('core:manage_associate_reports')

