#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- 🔍 DIAGNOSTIC DE PRODUCTION ---"
echo "Python: $(python --version)"
echo "Current Directory: $(pwd)"
echo "DATABASE_URL: ${DATABASE_URL:0:15}..."

# 1. Diagnostic et Réparation de la base
echo "⚙️ Initialisation et réparation de la base de données..."
python init_db.py

# 2. Migrations générales
echo "📂 Application des migrations générales..."
python manage.py migrate --noinput --fake-initial

# 3. Assets
echo "📦 Collecte des assets..."
mkdir -p staticfiles
python manage.py collectstatic --noinput --clear
chmod -R 755 staticfiles

# 4. Gunicorn
echo "📡 Démarrage..."
exec gunicorn app:app --log-file - --access-logfile - --workers 2 --timeout 120
