#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🚀 Démarrage de la phase Runtime..."

# 1. Exécution des migrations (Garantit que les tables existent)
echo "📂 Application des migrations..."
python manage.py migrate --noinput

# 2. Lancement du serveur
echo "📡 Démarrage de Gunicorn..."
gunicorn app:app
