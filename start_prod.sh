#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- 🔍 DIAGNOSTIC DE PRODUCTION ---"
echo "Python: $(python --version)"
echo "Current Directory: $(pwd)"
echo "DATABASE_URL: ${DATABASE_URL:0:15}..."

# 1. Vérification des migrations
echo "📂 État des migrations..."
python manage.py showmigrations sessions

echo "⚙️ Application des migrations..."
python manage.py migrate --noinput

# 2. Vérification des fichiers statiques
echo "📦 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear

# 3. Lancement de Gunicorn
echo "📡 Démarrage de Gunicorn..."
exec gunicorn app:app --log-file -
