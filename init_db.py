import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quick_transfert.settings')
django.setup()

from django.db import connection, transaction
from django.core.management import call_command

def fix_database():
    db_settings = connection.settings_dict
    print(f"--- 🩺 DIAGNOSTIC BASE DE DONNÉES ---")
    print(f"Host: {db_settings.get('HOST')}")
    print(f"Database: {db_settings.get('NAME')}")
    
    with connection.cursor() as cursor:
        # 1. Lister les tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables actuelles : {', '.join(tables) if tables else 'Aucune'}")

        # 2. Force creation of session table if missing
        if 'django_session' not in tables:
            print("⚠️ Table 'django_session' manquante. Création forcée...")
            try:
                # On tente un migrate spécifique
                call_command('migrate', 'sessions', interactive=False)
                print("✅ Migration des sessions réussie.")
            except Exception as e:
                print(f"❌ Échec migration session : {e}")
                print("🛠️ Tentative de création via SQL brut...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS django_session (
                        session_key varchar(40) NOT NULL PRIMARY KEY,
                        session_data text NOT NULL,
                        expire_date timestamptz NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS django_session_expire_date_a5c62663 ON django_session (expire_date);
                """)
                print("✅ Table session créée via SQL brut.")

        # 3. Initialisation des données vitales
        from core.models import SystemSettings, Devise
        from decimal import Decimal
        
        print("🛠️ Initialisation des données système...")
        SystemSettings.get_settings()
        Devise.objects.get_or_create(code='USD', defaults={'taux_reference_usd': Decimal('1.0000')})
        Devise.objects.get_or_create(code='CDF', defaults={'taux_reference_usd': Decimal('0.0004')})
        print("✅ Données initialisées.")

if __name__ == "__main__":
    try:
        fix_database()
    except Exception as e:
        print(f"💥 Erreur critique lors de l'init : {e}")
        sys.exit(1)
