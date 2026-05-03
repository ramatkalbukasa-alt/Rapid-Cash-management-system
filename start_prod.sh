#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- 🔍 DIAGNOSTIC DE PRODUCTION ---"
echo "Python: $(python --version)"
echo "Current Directory: $(pwd)"
echo "DATABASE_URL: ${DATABASE_URL:0:15}..."

# 1. Diagnostic et Migrations
echo "📊 État de la base de données..."
python manage.py migrate --noinput --fake-initial

# Vérification explicite de la table session
echo "🔍 Vérification de la table session..."
python manage.py shell <<EOF
from django.db import connection
tables = connection.introspection.table_names()
if 'django_session' not in tables:
    print("⚠️ Table session manquante ! Tentative de création forcée...")
    from django.core.management import call_command
    call_command('migrate', 'sessions', '--fake-initial')
else:
    print("✅ Table session présente.")
EOF

# 2. Initialisation des données critiques
echo "🛠️ Initialisation des données..."
python manage.py shell <<EOF
from core.models import SystemSettings, Devise
from decimal import Decimal
SystemSettings.get_settings()
Devise.objects.get_or_create(code='USD', defaults={'taux_reference_usd': Decimal('1.0000')})
Devise.objects.get_or_create(code='CDF', defaults={'taux_reference_usd': Decimal('0.0004')})
EOF

# 3. Assets
echo "📦 Collecte des assets..."
mkdir -p staticfiles
python manage.py collectstatic --noinput --clear
chmod -R 755 staticfiles

# 4. Gunicorn
echo "📡 Démarrage..."
exec gunicorn app:app --log-file - --access-logfile - --workers 2 --timeout 120
