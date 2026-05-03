#!/bin/bash
set -o errexit

pip install -r requirements.txt

mkdir -p staticfiles
python manage.py collectstatic --noinput --clear
python manage.py migrate

# Create superuser if DB is empty (optional)
# python manage.py shell < create_admin.py
