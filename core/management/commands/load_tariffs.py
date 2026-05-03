from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import ZoneTarif, Tarif, Devise

class Command(BaseCommand):
    help = 'Populate tariffs for Rapid Cash transactions'

    def handle(self, *args, **options):
        # Ensure default zone exists
        zone, created = ZoneTarif.objects.get_or_create(
            nom='Standard',
            defaults={}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created zone: {zone.nom}'))
        
        # Ensure USD currency exists
        usd, _ = Devise.objects.get_or_create(
            code='USD',
            defaults={'taux_reference_usd': Decimal('1.0000')}
        )
        
        # Clear existing tariffs for the zone
        Tarif.objects.filter(zone=zone).delete()
        self.stdout.write(self.style.WARNING(f'Cleared existing tariffs for zone: {zone.nom}'))
        
        # Tariff structure provided by the user
        tariffs = [
            (Decimal('0.10'), Decimal('40.00'), Decimal('5.00')),
            (Decimal('40.10'), Decimal('100.00'), Decimal('8.00')),
            (Decimal('100.10'), Decimal('200.00'), Decimal('15.00')),
            (Decimal('200.10'), Decimal('300.00'), Decimal('20.00')),
            (Decimal('300.10'), Decimal('400.00'), Decimal('26.00')),
            (Decimal('400.10'), Decimal('600.00'), Decimal('30.00')),
            (Decimal('600.10'), Decimal('800.00'), Decimal('35.00')),
            (Decimal('800.10'), Decimal('1000.00'), Decimal('40.00')),
            (Decimal('1000.10'), Decimal('1500.00'), Decimal('45.00')),
            (Decimal('1500.10'), Decimal('1800.00'), Decimal('64.00')),
            (Decimal('1800.10'), Decimal('2000.00'), Decimal('80.00')),
        ]
        
        for montant_min, montant_max, frais_fixe in tariffs:
            tarif, created = Tarif.objects.get_or_create(
                zone=zone,
                montant_min=montant_min,
                montant_max=montant_max,
                defaults={'frais_fixe': frais_fixe}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created tariff: ${montant_min} - ${montant_max} -> ${frais_fixe}'
                    )
                )
        
        self.stdout.write(self.style.SUCCESS('\n✅ All tariffs loaded successfully!'))
