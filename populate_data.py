import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')  # RAPID CASH
django.setup()

from core.models import ZoneTarif, Tarif, Devise

def populate():
    # Devises
    usd, _ = Devise.objects.get_or_create(code='USD', defaults={'taux_reference_usd': 1.0})
    Devise.objects.get_or_create(code='EUR', defaults={'taux_reference_usd': 1.08})
    Devise.objects.get_or_create(code='GBP', defaults={'taux_reference_usd': 1.26})
    Devise.objects.get_or_create(code='CDF', defaults={'taux_reference_usd': 0.00036})
    Devise.objects.get_or_create(code='TRY', defaults={'taux_reference_usd': 0.031})

    # Zones
    standard_zone, _ = ZoneTarif.objects.get_or_create(nom='Standard')
    nord_congo_zone, _ = ZoneTarif.objects.get_or_create(nom='Nord-Congo')

    # Standard Tariffs
    standard_data = [
        (0, 40, 5), (41, 100, 8), (101, 200, 15), (201, 300, 20),
        (301, 400, 26), (401, 600, 30), (601, 800, 35), (801, 1000, 40),
        (1001, 1200, 45), (1201, 1500, 64), (1501, 1800, 81), (1801, 2000, 90),
        (2001, 2400, 100), (2401, 2800, 115), (2801, 3200, 130), (3201, 3600, 145),
        (3601, 4000, 160)
    ]

    # Nord-Congo Tariffs
    nord_congo_data = [
        (0, 40, 6), (41, 100, 10), (101, 200, 17), (201, 300, 23),
        (301, 400, 29), (401, 600, 34), (601, 800, 39), (801, 1000, 44),
        (1001, 1200, 49), (1201, 1500, 68), (1501, 1800, 85), (1801, 2000, 94),
        (2001, 2400, 105), (2401, 2800, 120), (2801, 3200, 135), (3201, 3600, 150),
        (3601, 4000, 165)
    ]

    for min_v, max_v, fee in standard_data:
        Tarif.objects.get_or_create(zone=standard_zone, montant_min=min_v, montant_max=max_v, defaults={'frais_fixe': fee})

    for min_v, max_v, fee in nord_congo_data:
        Tarif.objects.get_or_create(zone=nord_congo_zone, montant_min=min_v, montant_max=max_v, defaults={'frais_fixe': fee})

    print("Données de tarifs et devises peuplées avec succès.")

if __name__ == "__main__":
    populate()
