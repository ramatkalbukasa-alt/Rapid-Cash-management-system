# ?? RAPID CASH

RAPID CASH est un système de gestion de transferts financiers et de caisses, conçu pour les administrateurs, agents, associés et investisseurs.

## Fonctionnalités clés

- Gestion des transactions de **transfert** et **retrait**
- Calcul automatique des frais selon les tarifs définis
- Support multi-devises et conversion vers USD
- Gestion des caisses par agent
- Suivi des commissions et performance des agents
- Journal d'audit immuable pour toutes les modifications
- Export CSV et Excel des transactions
- Interface d'administration complète
- **API REST** minimale pour intégration externe

## Installation rapide

1. Ouvrir le projet :
```powershell
cd "c:\Users\User\Desktop\Quick transfert"
```

2. Activer l'environnement :
```powershell
.\venv\Scripts\Activate.ps1
```

3. Installer les dépendances :
```powershell
pip install -r requirements.txt
```

4. Configurer les variables d'environnement :
```powershell
$env:DEBUG = "True"
$env:DJANGO_SECRET_KEY = "your-secret-key"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
```

5. Démarrer le serveur :
```powershell
python manage.py runserver
```

Le site est disponible sur `http://127.0.0.1:8000/`.

## Routes importantes

| URL | Description |
|---|---|
| `/` | Redirection vers le tableau de bord selon le rôle |
| `/admin-dashboard/` | Tableau de bord administrateur |
| `/agent-dashboard/` | Tableau de bord agent |
| `/associe-dashboard/` | Tableau de bord associé |
| `/investisseur-dashboard/` | Tableau de bord investisseur |
| `/manage-users/` | Gestion des utilisateurs |
| `/system-settings/` | Paramètres système |
| `/transaction-management/` | Gestion avancée des transactions |
| `/export/transactions/csv/` | Export CSV |
| `/export/transactions/excel/` | Export Excel |

## API REST

L'API REST utilise des jetons d'API (`Token <clé>`) avec des permissions basées sur `APIToken`.

### Points de terminaison

- `GET /core/api/transactions/` : liste des transactions
- `POST /core/api/transactions/` : création d'une transaction
- `GET /core/api/transactions/<id>/` : détails d'une transaction
- `GET /core/api/system-settings/` : configuration système

### En-tête d'authentification

Ajoutez ce header à vos requêtes :
```
Authorization: Token <votre_token_api>
```

### Exemple de création de transaction

```bash
curl -X POST "http://127.0.0.1:8000/core/api/transactions/" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 2,
    "type_operation": "TRANSFERT",
    "montant": "120.00",
    "zone_id": 1,
    "observation": "API transfer"
  }'
```

## Sécurité API

- Les jetons doivent être actifs et ne pas être expirés.
- La fonctionnalité API doit être activée dans les paramètres système.
- Les permissions d'API sont contrôlées via le modèle `APIToken`.

## Maintenance

- Les paramètres système sont disponibles à `/core/system-settings/`.
- Les transactions peuvent être recherchées, filtrées et modifiées par l'administrateur.
- Les journaux d'audit conservent toutes les modifications importantes.

---

## Notes

Le projet est configuré pour fonctionner dans un environnement Windows avec Django 4.2.9 et Python 3.11.

Pour toute modification dans le code, exécutez :
```powershell
python manage.py check
```
