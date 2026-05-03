# 📧 GMAIL SMTP SETUP GUIDE FOR DJANGO

## 🔧 Step 1: Enable 2-Factor Authentication on Gmail

1. Go to https://myaccount.google.com/security
2. Click **2-Step Verification**
3. Follow Google's setup process
4. Confirm your phone number

---

## 🔑 Step 2: Generate App Password

1. After enabling 2FA, go back to https://myaccount.google.com/security
2. Scroll to **App passwords**
3. Select:
   - **App:** Mail
   - **Device:** Windows Computer (or your device)
4. Click **Generate**
5. **Copy the 16-character password** (it will be like: `xxxx xxxx xxxx xxxx`)

---

## 📝 Step 3: Update `.env` Local File

Create/Update `.env` in your project root:

```env
# Django
DEBUG=true
DJANGO_SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Email Configuration (Gmail)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

**Replace:**
- `your-email@gmail.com` → Your actual Gmail address
- `xxxx xxxx xxxx xxxx` → The 16-character App Password (keep the spaces)

---

## 🚀 Step 4: Test Locally

Run this Python command to test:

```bash
cd "c:\Users\User\Desktop\Quick transfert"
python manage.py shell
```

Then in Django shell:

```python
from django.core.mail import send_mail

send_mail(
    subject='Test Email from Django',
    message='If you receive this, email is working!',
    from_email='your-email@gmail.com',
    recipient_list=['your-email@gmail.com'],
    fail_silently=False,
)
```

Expected output:
```
1  # ← Means 1 email sent successfully
```

Exit shell:
```python
exit()
```

---

## ☁️ Step 5: Deploy to Render

### Option A: Using Render Dashboard UI

1. Go to **Render Dashboard** → Your Web Service
2. **Environment** tab → **Add Environment Variable**
3. Add these variables:

| Key | Value |
|-----|-------|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `true` |
| `EMAIL_HOST_USER` | `your-email@gmail.com` |
| `EMAIL_HOST_PASSWORD` | `xxxx xxxx xxxx xxxx` |

4. **Save** → **Manual Deploy**

### Option B: Via render.yaml (Recommended for DevOps)

The file already has structure ready in `render.yaml`

---

## 🔒 Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` to Git (already in `.gitignore`)
- Gmail App Passwords are just like passwords - keep them secret
- On Render, use **Environment Variables** (not in code)
- For production: Consider using SendGrid, Mailgun, or AWS SES instead of Gmail (more reliable for production)

---

## 🧪 Testing in Production (Render)

After deploying, test sending email via Django admin:

1. Go to `https://your-app.onrender.com/admin/`
2. Create a test user with an email
3. In Render Shell, run:

```bash
python manage.py shell
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.first()
from django.core.mail import send_mail
send_mail('Test', 'Hello from Render!', 'your-email@gmail.com', [user.email])
```

---

## 🆘 Troubleshooting

### "SMTPAuthenticationError: Invalid credentials"
→ Check Gmail App Password is correct (16 chars with spaces)
→ Verify 2FA is enabled on Gmail account

### "SMTPNotSupportedError: STARTTLS extension not supported"
→ Ensure `EMAIL_USE_TLS=true` in environment variables

### "smtplib.SMTPException: SMTP AUTH extension not supported"
→ Try changing EMAIL_PORT to 465 with `EMAIL_USE_SSL=true` instead of TLS

### Emails not sent but no error
→ Check Django is using SMTP backend, not Console backend
→ Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set

---

## 📧 Usage in Django Code

### Send Welcome Email (Example)

```python
from django.core.mail import send_mail
from django.template.loader import render_to_string

# Send simple email
send_mail(
    subject='Welcome to Quick Transfert',
    message='Account created successfully!',
    from_email='your-email@gmail.com',
    recipient_list=['user@example.com'],
    fail_silently=False,
)

# Send HTML email with template
html_message = render_to_string('email_template.html', context)
send_mail(
    subject='Quick Transfert Report',
    message='See HTML version',
    from_email='your-email@gmail.com',
    recipient_list=['user@example.com'],
    html_message=html_message,
    fail_silently=False,
)
```

---

## 🎯 Next Steps

1. ✅ Enable Gmail 2FA
2. ✅ Generate App Password
3. ✅ Update `.env` locally
4. ✅ Test with `python manage.py shell`
5. ✅ Commit and push to GitHub
6. ✅ Add Environment Variables in Render
7. ✅ Redeploy on Render
8. ✅ Test in production

**All set!** 🎉 Your Django app can now send emails via Gmail SMTP!
