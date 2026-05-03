import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')  # RAPID CASH
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin', role='ADMINISTRATEUR')
    print("Superuser created successfully.")
else:
    print("Superuser already exists.")
