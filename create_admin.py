import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')
django.setup()

User = get_user_model()

def create_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
    
    if not User.objects.filter(username=username).exists():
        print(f"👤 Création du superuser : {username}...")
        # Use create_superuser from manager
        User.objects.create_superuser(username=username, email=email, password=password, role='ADMINISTRATEUR')
        print("✅ Superuser créé avec succès.")
    else:
        print(f"ℹ️ Le superuser '{username}' existe déjà. Saut de l'étape.")

if __name__ == "__main__":
    create_superuser()
