#!/bin/bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput

# Create superuser if DB is empty (optional)
# python manage.py shell < create_admin.py
