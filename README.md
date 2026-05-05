# ?? RAPID CASH

RAPID CASH est un syst�me de gestion de transferts financiers et de caisses, con�u pour les administrateurs, agents, associ�s et investisseurs.

## Fonctionnalit�s cl�s

- Gestion des transactions de **transfert** et **retrait**
- Calcul automatique des frais selon les tarifs d�finis
- Support multi-devises et conversion vers USD
- Gestion des caisses par agent
- Suivi des commissions et performance des agents
- Journal d'audit immuable pour toutes les modifications
- Export CSV et Excel des transactions
- Interface d'administration compl�te
- **API REST** minimale pour int�gration externe

## Installation rapide

1. Ouvrir le projet :
```powershell
cd "c:\Users\User\Desktop\Quick transfert"
```

2. Activer l'environnement :
```powershell
.\venv\Scripts\Activate.ps1
```

3. Installer les d�pendances :
```powershell
pip install -r requirements.txt
```

4. Configurer les variables d'environnement :
```powershell
$env:DEBUG = "True"
$env:DJANGO_SECRET_KEY = "your-secret-key"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
```

5. D�marrer le serveur :
```powershell
python manage.py runserver
```

Le site est disponible sur `http://127.0.0.1:8000/`.

## Routes importantes

| URL | Description |
|---|---|
| `/` | Redirection vers le tableau de bord selon le r�le |
| `/admin-dashboard/` | Tableau de bord administrateur |
| `/agent-dashboard/` | Tableau de bord agent |
| `/associe-dashboard/` | Tableau de bord associ� |
| `/investisseur-dashboard/` | Tableau de bord investisseur |
| `/manage-users/` | Gestion des utilisateurs |
| `/system-settings/` | Param�tres syst�me |
| `/transaction-management/` | Gestion avanc�e des transactions |
| `/export/transactions/csv/` | Export CSV |
| `/export/transactions/excel/` | Export Excel |

## API REST

L'API REST utilise des jetons d'API (`Token <cl�>`) avec des permissions bas�es sur `APIToken`.

### Points de terminaison

- `GET /core/api/transactions/` : liste des transactions
- `POST /core/api/transactions/` : cr�ation d'une transaction
- `GET /core/api/transactions/<id>/` : d�tails d'une transaction
- `GET /core/api/system-settings/` : configuration syst�me

### En-t�te d'authentification

Ajoutez ce header � vos requ�tes :
```
Authorization: Token <votre_token_api>
```

### Exemple de cr�ation de transaction

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

## S�curit� API

- Les jetons doivent �tre actifs et ne pas �tre expir�s.
- La fonctionnalit� API doit �tre activ�e dans les param�tres syst�me.
- Les permissions d'API sont contr�l�es via le mod�le `APIToken`.

## Maintenance

- Les param�tres syst�me sont disponibles � `/core/system-settings/`.
- Les transactions peuvent �tre recherch�es, filtr�es et modifi�es par l'administrateur.
- Les journaux d'audit conservent toutes les modifications importantes.

---

## Notes

Le projet est configur� pour fonctionner dans un environnement Windows avec Django 4.2.9 et Python 3.11.

Pour toute modification dans le code, ex�cutez :
```powershell
python manage.py check
```
