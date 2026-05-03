# 🚀 GUIDE DE DÉPLOIEMENT - QUICK TRANSFERT SUR RENDER

## ✅ PRÉ-REQUIS

- Compte GitHub (pousser le code)
- Compte Render.com (gratuit: https://render.com)
- PostgreSQL sera créé automatiquement par Render

---

## 📋 ÉTAPES DE DÉPLOIEMENT

### **ÉTAPE 1: Préparer le repository Git**

```bash
# Initialiser Git si ce n'est pas fait
git init
git add .
git commit -m "Initial commit - Ready for Render deployment"

# Pousser sur GitHub
git remote add origin https://github.com/YOUR_USERNAME/quick-transfert.git
git branch -M main
git push -u origin main
```

### **ÉTAPE 2: Créer un service Web sur Render**

1. **Aller sur** https://render.com et se connecter
2. **Dashboard** → **New +** → **Web Service**
3. **Connecter** votre repository GitHub
4. **Configurer:**
   - **Name:** `quick-transfert` (ou votre choix)
   - **Branch:** `main`
   - **Build Command:** `bash build.sh`
   - **Start Command:** `gunicorn quick_transfert.wsgi --workers 1`
   - **Region:** Frankfurt (pour latence basse en Afrique)
   - **Plan:** Free (puis Scale après)

### **ÉTAPE 3: Ajouter Environment Variables**

Dans Render Dashboard → Web Service → Environment:

```env
DEBUG=false
DJANGO_SECRET_KEY=GENERATE_WITH_PYTHON_SECRETS
ALLOWED_HOSTS=your-app-name.onrender.com
PYTHON_VERSION=3.11
```

**Générer une clé sécurisée:**
```python
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### **ÉTAPE 4: Créer la Base de Données PostgreSQL**

Dans Render Dashboard → **New +** → **PostgreSQL**

1. **Configurer:**
   - **Name:** `quick-transfert-db`
   - **Database Name:** `quick_transfert`
   - **User:** `postgres`
   - **Region:** Frankfurt
   - **Version:** 15
   - **Plan:** Free

2. **Render va générer automatiquement** `DATABASE_URL`

3. **Ajouter à l'Environment du Web Service:**
   - Copier le `DATABASE_URL` fourni par Render
   - Ajouter à **Environment Variables** du Web Service

### **ÉTAPE 5: Migration et Setup Initial**

Render exécutera automatiquement:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### **ÉTAPE 6: Créer Superuser (Admin)**

**Via Shell Render:**
1. Aller au Web Service → **Shell**
2. Exécuter:
```bash
python manage.py createsuperuser
```

Ou créer automatiquement avec `create_admin.py` (optionnel dans build.sh)

### **ÉTAPE 7: Tester**

1. Accéder à votre app: `https://your-app-name.onrender.com`
2. Tester login admin: `/admin/`
3. Vérifier les logs: Dashboard → Logs

---

## 🔐 SÉCURITÉ - CHECKLIST IMPORTANT

- [ ] `DEBUG=false` en production ✅
- [ ] `SECRET_KEY` générée aléatoirement ✅
- [ ] PostgreSQL au lieu de SQLite ✅
- [ ] ALLOWED_HOSTS configuré ✅
- [ ] WhiteNoise pour assets statiques ✅
- [ ] HTTPS activé par défaut sur Render ✅
- [ ] Media files → Ajouter storage (S3/Cloudinary) si besoin

---

## 📊 ARCHITECTURE FINALE

```
┌─────────────────┐
│  GitHub Repo    │
│                 │
│ - Django code   │
│ - Templates     │
│ - Static files  │
└────────┬────────┘
         │
         ↓ (Render detects push)
┌─────────────────────────────────┐
│  RENDER WEB SERVICE             │
│                                  │
│ 1. git clone                    │
│ 2. bash build.sh                │
│    - pip install               │
│    - collectstatic             │
│    - migrate                   │
│ 3. Start: gunicorn             │
└─────────┬───────────────────────┘
          │
          ├──→ PostgreSQL Database
          │
          ├──→ Nginx Reverse Proxy
          │
          ├──→ SSL Certificate
          │
          └──→ Public URL
```

---

## 🆘 TROUBLESHOOTING

### **"ModuleNotFoundError: No module named 'X'"**
→ Ajouter package à `requirements.txt` et redéployer

### **"Static files not found (404)"**
→ Vérifier `STATIC_ROOT` et `STATIC_URL` dans settings.py

### **"Cannot connect to database"**
→ Vérifier `DATABASE_URL` dans Environment Variables

### **"Secret key error"**
→ Générer nouvelle clé et mettre en `DJANGO_SECRET_KEY`

### **"Permission denied" sur /media/**
→ Configurer S3/Cloudinary pour media files (recommandé en production)

---

## 🚀 COMMANDES UTILES

**Déployer manuellement:**
```bash
git push origin main  # Render détecte et redéploie auto
```

**SSH dans l'app (Debug):**
```
Render Dashboard → Web Service → Shell
```

**Voir les logs:**
```
Render Dashboard → Web Service → Logs
```

**Redémarrer l'app:**
```
Render Dashboard → Web Service → Manual Deploy (ou push code)
```

---

## 💰 COÛTS RENDER

- **Free Tier:** $0/mois (limité, peut démarrer/arrêter)
- **PostgreSQL Free:** Gratuit première instance
- **Paid:** ~$7/mois pour production stable

**Recommandation:** Tester sur Free, puis passer à Starter ($7+) pour production.

---

## 📚 RESSOURCES

- Render Docs: https://render.com/docs
- Django Deployment: https://docs.djangoproject.com/en/4.2/howto/deployment/
- WhiteNoise: http://whitenoise.evans.io/

---

**✅ Vous êtes prêt! Pusher votre code et Render s'occupera du reste! 🎉**
