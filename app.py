import os
from django.core.wsgi import get_wsgi_application

# Set the default Django settings module for the 'gunicorn app:app' default.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')

application = get_wsgi_application()
app = application # Alias for Render's default 'app:app'
