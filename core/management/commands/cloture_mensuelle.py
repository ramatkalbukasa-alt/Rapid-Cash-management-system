"""
Management command for automatic monthly closing.
Calculates associate revenue sharing and generates reports.
Run this at the end of each month (via cron/scheduler or manually).

Usage: python manage.py cloture_mensuelle
       python manage.py cloture_mensuelle --mois 5 --annee 2026
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal

from core.models import (
    ContratPartenaire, RapportMensuelAssocie, Transaction,
    StatutTransaction, TypeContrat, Role, CustomUser
)


class Command(BaseCommand):
    help = "Clôture mensuelle : calcule les bénéfices des associés et génère les rapports."

    def add_arguments(self, parser):
        parser.add_argument('--mois', type=int, help="Mois à clôturer (1-12)")
        parser.add_argument('--annee', type=int, help="Année à clôturer")

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Default: previous month
        if options['mois'] and options['annee']:
            mois = options['mois']
            annee = options['annee']
        else:
            # Calculate previous month
            if now.month == 1:
                mois = 12
                annee = now.year - 1
            else:
                mois = now.month - 1
                annee = now.year

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"  CLÔTURE MENSUELLE - {mois:02d}/{annee}")
        self.stdout.write(f"{'='*60}\n")

        # Process all active ASSOCIE contracts
        contrats_associes = ContratPartenaire.objects.filter(
            type_contrat=TypeContrat.ASSOCIE,
            statut='ACTIF'
        )

        reports_created = 0
        reports_skipped = 0

        for contrat in contrats_associes:
            # Check if report already exists
            if RapportMensuelAssocie.objects.filter(
                contrat=contrat, mois=mois, annee=annee
            ).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  [SKIP] Rapport déjà existant pour {contrat.partenaire.username} ({mois}/{annee})"
                    )
                )
                reports_skipped += 1
                continue

            # Get all COMPLETED transactions by this associate for the month
            from django.utils.timezone import make_aware
            from datetime import datetime
            
            start_date = make_aware(datetime(annee, mois, 1))
            if mois == 12:
                end_date = make_aware(datetime(annee + 1, 1, 1))
            else:
                end_date = make_aware(datetime(annee, mois + 1, 1))

            transactions = Transaction.objects.filter(
                agent=contrat.partenaire,
                statut=StatutTransaction.COMPLETED,
                date__gte=start_date,
                date__lt=end_date
            )

            nombre_ops = transactions.count()
            volume = transactions.aggregate(
                total=Sum('montant_reference')
            )['total'] or Decimal('0.00')
            total_frais = transactions.aggregate(
                total=Sum('frais_reference')
            )['total'] or Decimal('0.00')

            # Calculate revenue sharing
            pourcentage_rc = contrat.pourcentage_partage_rc
            montant_rc = (total_frais * pourcentage_rc / Decimal('100')).quantize(Decimal('0.01'))
            montant_associe = (total_frais - montant_rc).quantize(Decimal('0.01'))

            # Create the monthly report
            rapport = RapportMensuelAssocie.objects.create(
                contrat=contrat,
                mois=mois,
                annee=annee,
                nombre_operations=nombre_ops,
                volume_operations=volume,
                total_frais_collectes=total_frais,
                pourcentage_rc=pourcentage_rc,
                montant_rc=montant_rc,
                montant_associe=montant_associe,
                observation=f"Clôture automatique - {nombre_ops} opérations traitées"
            )

            reports_created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] {contrat.partenaire.username}: "
                    f"{nombre_ops} ops | Frais: ${total_frais} | "
                    f"RC ({pourcentage_rc}%): ${montant_rc} | "
                    f"Associé: ${montant_associe}"
                )
            )

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"  RÉSUMÉ: {reports_created} rapport(s) créé(s), {reports_skipped} ignoré(s)")
        self.stdout.write(f"{'='*60}\n")
