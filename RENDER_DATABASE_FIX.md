# 🚨 RENDER DATABASE CONNECTION FIX

Your application is currently failing because it's using **SQLite** instead of **PostgreSQL** on Render. Since Render's disk is temporary, the SQLite database is reset or empty every time the app starts, leading to the `no such table: django_session` error.

## 🛠️ HOW TO FIX THIS

### Step 1: Find your Database URL
1. Go to your **Render Dashboard**.
2. Click on your PostgreSQL database (e.g., **quick_transfert_db**).
3. Scroll down to the **"Connection"** section.
4. Copy the **"Internal Database URL"**. It should look like `postgres://user:password@hostname:port/database`.

### Step 2: Add it to your Web Service
1. Go back to your **Render Dashboard**.
2. Click on your Web Service (**quick-transfert**).
3. Go to the **Settings** tab.
4. Scroll down to the **"Environment Variables"** section.
5. Click **"Add Environment Variable"**.
6. **Key:** `DATABASE_URL`
7. **Value:** (Paste the URL you copied in Step 1).
8. Click **"Save Changes"**.

### Step 3: Verify Deployment
1. Once you save the changes, Render will automatically redeploy.
2. Watch the **Logs**. You should see the `releaseCommand` running migrations:
   ```
   ==> Running 'python manage.py migrate'
   Operations to perform:
     Apply all migrations: admin, auth, contenttypes, core, sessions, ...
     ...
   ```
3. Once the deployment is live, your site should work!

## 🔍 WHY DID THIS HAPPEN?
- **Render Blueprints:** If you didn't create your service via a "Blueprint" (using the `render.yaml` file), Render doesn't automatically link your database to your web service.
- **Manual Setup:** If you set up the web service manually, you must manually provide the `DATABASE_URL` so Django knows how to connect to PostgreSQL.
- **SQLite Fallback:** My latest code change in `settings.py` now prevents Django from silently falling back to SQLite on Render. It will now show a clear error if `DATABASE_URL` is missing, which is easier to debug.

---
*Generated: May 3, 2026*
