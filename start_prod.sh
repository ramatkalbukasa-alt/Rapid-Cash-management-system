#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- 🔍 DIAGNOSTIC DE PRODUCTION ---"
echo "Python: $(python --version)"
echo "Current Directory: $(pwd)"
echo "DATABASE_URL: ${DATABASE_URL:0:15}..."

# 1. État de la base et migrations
echo "⚙️ Application des migrations..."
python manage.py migrate --noinput

# 2. Initialisation automatique des données critiques
echo "🛠️ Initialisation des données système..."
python manage.py shell <<EOF
from core.models import SystemSettings, Devise
from decimal import Decimal
# Créer les paramètres par défaut
SystemSettings.get_settings()
# Créer les devises de base si absentes
Devise.objects.get_or_create(code='USD', defaults={'taux_reference_usd': Decimal('1.0000')})
Devise.objects.get_or_create(code='CDF', defaults={'taux_reference_usd': Decimal('0.0004')})
print("Initialisation terminée.")
EOF

# 3. Réparation des fichiers statiques
echo "📦 Collecte et réparation des fichiers statiques..."
mkdir -p staticfiles
python manage.py collectstatic --noinput --clear
chmod -R 755 staticfiles

# 4. Lancement de Gunicorn
echo "📡 Démarrage de Gunicorn..."
exec gunicorn app:app --log-file - --access-logfile -
