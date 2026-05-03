from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.db.models import Sum
from django.utils import timezone
from .models import Role, Transaction, Depense, CustomUser, StatutTransaction, TypeOperation
import logging

logger = logging.getLogger(__name__)


def _is_admin_or_agent(user):
    return user.is_authenticated and user.role in [Role.ADMIN, Role.AGENT]


@login_required
def generate_report(request, period):
    user = request.user

    # Fix #8 — Reject partners early with 403
    if user.role in [Role.ASSOCIE, Role.INVESTISSEUR]:
        return HttpResponse("Les relevés partenaires sont disponibles sur votre tableau de bord.", status=403)

    now = timezone.now()
    if period == 'daily':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title = f"Rapport Journalier - {now.strftime('%d/%m/%Y')}"
    elif period == 'monthly':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        title = f"Rapport Mensuel - {now.strftime('%B %Y')}"
    elif period == 'quarterly':
        # Go back to the start of the current quarter
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        start_date = now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        quarter_num = (now.month - 1) // 3 + 1
        title = f"Rapport Trimestriel - T{quarter_num} {now.strftime('%Y')}"
    elif period == 'yearly':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        title = f"Rapport Annuel - {now.strftime('%Y')}"
    else:  # 'global' or any unknown value
        start_date = None
        title = "Rapport Global — Toutes Opérations"

    # Fix #2 — Only count COMPLETED transactions in all aggregates
    txs = Transaction.objects.filter(statut=StatutTransaction.COMPLETED)
    # Fix #3 — Use .date() for DateField comparison (Depense.date is a DateField)
    deps = Depense.objects.all()
    if start_date:
        txs = txs.filter(date__gte=start_date)
        deps = deps.filter(date__gte=start_date.date())

    # Role-specific filtering
    if user.role == Role.AGENT:
        txs = txs.filter(agent=user)
        deps = deps.none()

    volume = txs.aggregate(total=Sum('montant_reference'))['total'] or 0
    frais = txs.aggregate(total=Sum('frais_reference'))['total'] or 0

    # Fix #1 — Convert depenses to USD before subtracting (each expense has its own devise)
    depenses_usd = sum(
        dep.montant * dep.devise.taux_reference_usd
        for dep in deps.select_related('devise')
    )

    commissions = 0
    if user.role == Role.ADMIN:
        agents = CustomUser.objects.filter(role=Role.AGENT)
        for agent in agents:
            # Fix #5 — Commissions only on TRANSFERT, not RETRAIT
            agent_txs = txs.filter(agent=agent, type_operation=TypeOperation.TRANSFERT)
            frais_agent = agent_txs.aggregate(total=Sum('frais_reference'))['total'] or 0
            try:
                pct = agent.agent_profile.commission_pourcentage
                commissions += (frais_agent * pct / 100)
            except Exception:
                pass
    elif user.role == Role.AGENT:
        try:
            # Fix #5 — Commissions only on TRANSFERT
            frais_transfert = txs.filter(
                type_operation=TypeOperation.TRANSFERT
            ).aggregate(total=Sum('frais_reference'))['total'] or 0
            pct = user.agent_profile.commission_pourcentage
            commissions = (frais_transfert * pct / 100)
        except Exception:
            pass

    benefice = frais - depenses_usd - commissions

    # Fix #7 — Detect truncation, pass warning flag
    all_txs_ordered = txs.order_by('-date')
    total_count = all_txs_ordered.count()
    transactions_display = all_txs_ordered[:100]
    truncated = total_count > 100

    # Format context variables for new template
    period_labels = {
        'daily': 'Journalier',
        'monthly': 'Mensuel',
        'quarterly': 'Trimestriel',
        'yearly': 'Annuel',
        'global': 'Global'
    }
    period_label = period_labels.get(period, 'Rapport')
    
    role_labels = {
        Role.ADMIN: 'Administrateur',
        Role.AGENT: 'Agent',
        Role.ASSOCIE: 'Associé',
        Role.INVESTISSEUR: 'Investisseur'
    }
    
    user_profile = f"{user.get_full_name()} ({role_labels.get(user.role, user.role)})"
    generation_date = now.strftime('%d/%m/%Y %H:%M')
    company_name = 'Quick Transfert'

    # Format KPI values
    def format_currency(value):
        return f"${value:,.2f}".replace(',', ' ')
    
    kpi_volume_total = format_currency(volume)
    kpi_frais = format_currency(frais)
    kpi_depenses_commissions = format_currency(depenses_usd + commissions)
    kpi_benefice_net = format_currency(benefice)
    
    # Format financial summary (admin only)
    resume_frais_brut = format_currency(frais)
    resume_depenses = format_currency(depenses_usd)
    resume_commissions = format_currency(commissions)
    resume_benefice_net = format_currency(benefice)

    # Base context for all roles
    base_context = {
        'title': title,
        'period': period,
        'period_label': period_label,
        'report_type_label': title,
        'generation_date': generation_date,
        'user_profile': user_profile,
        'company_name': company_name,
        'volume': volume,
        'frais': frais,
        'commissions': commissions,
        'transactions': transactions_display,
        'total_count': total_count,
        'truncated': truncated,
        'now': now,
        'user_role': user.role,
        'kpi_volume_total': kpi_volume_total,
        'kpi_frais': kpi_frais,
        'kpi_depenses_commissions': kpi_depenses_commissions,
        'kpi_benefice_net': kpi_benefice_net,
    }

    if user.role == Role.AGENT:
        context = base_context
    else:
        context = {
            **base_context,
            'depenses': depenses_usd,
            'benefice': benefice,
            'resume_frais_brut': resume_frais_brut,
            'resume_depenses': resume_depenses,
            'resume_commissions': resume_commissions,
            'resume_benefice_net': resume_benefice_net,
        }

    if request.GET.get('format') == 'pdf':
        try:
            from xhtml2pdf import pisa
            from io import BytesIO
            
            # For PDFs, export all transactions (no truncation)
            context['transactions'] = all_txs_ordered  # no limit
            context['truncated'] = False
            
            try:
                html_string = render_to_string('core/report_pdf.html', context, request=request)
            except Exception as e:
                logger.error(f"Template rendering error: {e}")
                return HttpResponse(f"Erreur lors du rendu du modèle: {str(e)}", status=500)
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="rapport_{period}.pdf"'
            
            try:
                pdf_buffer = BytesIO()
                pisa_status = pisa.CreatePDF(html_string, dest=pdf_buffer)
                if pisa_status.err:
                    logger.error(f"PDF generation error: {pisa_status.err}")
                    return HttpResponse(f"Erreur de génération PDF: {pisa_status.err}", status=500)
                pdf_buffer.seek(0)
                response.write(pdf_buffer.getvalue())
                return response
            except Exception as e:
                logger.error(f"PDF creation error: {e}", exc_info=True)
                return HttpResponse(f"Erreur lors de la création du PDF: {str(e)}", status=500)
        except ImportError:
            logger.error("xhtml2pdf is not installed")
            return HttpResponse("Le module xhtml2pdf n'est pas installé. Contactez l'administrateur.", status=500)
        except Exception as e:
            logger.error(f"Unexpected error in PDF generation: {e}", exc_info=True)
            return HttpResponse(f"Erreur inattendue: {str(e)}", status=500)

    elif request.GET.get('format') == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="rapport_{period}_{now.strftime("%Y%m%d")}.csv"'
        # BOM for Excel
        response.write(u'\ufeff'.encode('utf8'))
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['N° Transaction', 'Date', "Type d'opération", 'Montant', 'Devise', 'Frais Reference (USD)', 'Statut'])
        for tx in all_txs_ordered:
            date_str = timezone.localtime(tx.date).strftime('%d/%m/%Y %H:%M')
            writer.writerow([
                tx.numero_transaction,
                date_str,
                tx.get_type_operation_display(),
                str(tx.montant).replace('.', ','),
                tx.devise_origine.code,
                str(tx.frais_reference).replace('.', ','),
                tx.get_statut_display(),
            ])
        return response

    return render(request, 'core/report_view.html', context)
