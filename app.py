import os
import subprocess
import sys
from django.core.wsgi import get_wsgi_application

# 1. Configuration des réglages
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')

# 2. AUTO-RÉPARATION AU DÉMARRAGE (Nuclear Option)
# Cette partie s'exécute AVANT que Gunicorn ne commence à servir des requêtes
if os.environ.get('RENDER'):
    print("--- 🚀 DÉMARRAGE DE L'AUTO-RÉPARATION RENDER ---")
    try:
        # Lancement de init_db.py
        print("🛠️ Exécution de init_db.py...")
        subprocess.run([sys.executable, "init_db.py"], check=True)
        
        # Lancement des migrations
        print("📂 Application des migrations...")
        subprocess.run([sys.executable, "manage.py", "migrate", "--noinput", "--fake-initial"], check=True)
        
        # Création du superuser
        print("👤 Initialisation de l'administrateur...")
        subprocess.run([sys.executable, "create_admin.py"], check=True)
        
        # Collectstatic
        print("📦 Collecte des assets...")
        subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], check=True)
        
        print("✅ Auto-réparation terminée avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors de l'auto-réparation : {e}")

# 3. Initialisation de l'application WSGI standard
application = get_wsgi_application()
app = application
