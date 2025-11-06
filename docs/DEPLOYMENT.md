# Deployment Guide: Render + GoDaddy

This guide will walk you through deploying your Django/Wagtail online shop to Render and configuring your GoDaddy domain.

## Prerequisites
- [x] GitHub repository: `git@github.com:matt-rw/online-shop.git`
- [x] GoDaddy domain (previously linked to Shopify)
- [ ] Render account (free tier available)
- [ ] Stripe API keys (production keys)

---

## Part 1: Prepare for Deployment

### 1.1 Ensure .gitignore is correct
Your `.gitignore` should include:
```
venv
.venv
db.sqlite3
__pycache__/
.env
*.py[cod]
staticfiles/
media/
*.sqlite3
```

### 1.2 Push your code to GitHub
```bash
git add .
git commit -m "Prepare for production deployment"
git push origin master
```

---

## Part 2: Deploy to Render

### 2.1 Create Web Service on Render

1. Go to https://render.com and sign up/login
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `matt-rw/online-shop`
4. Configure the service:

   **Basic Settings:**
   - **Name**: `blueprint-apparel` (or your preferred name)
   - **Region**: Choose closest to your users (e.g., Oregon)
   - **Branch**: `master`
   - **Root Directory**: Leave blank
   - **Runtime**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn online_shop.wsgi:application`

   **Instance Type:**
   - Choose **Free** (or paid for better performance)

### 2.2 Add Environment Variables

In the Render dashboard, scroll to **Environment Variables** and add:

**Required:**
```
DJANGO_SETTINGS_MODULE=online_shop.settings.production
PYTHON_VERSION=3.8.0
SECRET_KEY=<click "Generate" to create a secure key>
DEBUG=False
```

**Stripe (use production keys):**
```
STRIPE_SECRET_KEY=sk_live_your_production_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_production_key
```

**Email (SMTP):**
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

**Optional (PostgreSQL - recommended for production):**
```
# If using Render PostgreSQL database:
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432
```

### 2.3 Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repo
   - Run `build.sh` (install deps, collect static, migrate)
   - Start gunicorn
3. Wait for deployment to complete (5-10 minutes)
4. Note your Render URL: `https://blueprint-apparel.onrender.com`

---

## Part 3: Configure GoDaddy DNS

### 3.1 Remove Shopify DNS Settings

1. Log into **GoDaddy** → **My Products** → **Domains**
2. Click your domain → **DNS** (or **Manage DNS**)
3. **Remove old Shopify records:**
   - Look for CNAME records pointing to `shops.myshopify.com`
   - Look for A records pointing to Shopify IPs
   - **Delete these records** (you can screenshot them first as backup)

### 3.2 Add Render DNS Records

Add the following DNS records:

**For root domain (blueprintapparel.store):**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | `216.24.57.1` | 600 |

**For www subdomain (www.blueprintapparel.store):**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | www | `blueprint-apparel.onrender.com` | 600 |

> **Note**: Replace `blueprint-apparel.onrender.com` with your actual Render domain.

### 3.3 DNS Propagation

- DNS changes can take **24-48 hours** to fully propagate
- Usually takes **15 minutes to 2 hours** in practice
- Test with: `dig blueprintapparel.store` or `nslookup blueprintapparel.store`

---

## Part 4: Configure Custom Domain in Render

1. In Render dashboard, go to your web service
2. Click **Settings** → **Custom Domains**
3. Click **"Add Custom Domain"**
4. Add both:
   - `blueprintapparel.store`
   - `www.blueprintapparel.store`
5. Render will automatically provision **free SSL certificates** (may take a few minutes)

---

## Part 5: Update Django Settings for Custom Domain

Once your domain is configured, you may need to update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in `online_shop/settings/production.py`:

```python
ALLOWED_HOSTS = [
    '.onrender.com',
    'blueprintapparel.store',
    'www.blueprintapparel.store'
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://blueprintapparel.store',
    'https://www.blueprintapparel.store',
]
```

Push these changes and Render will auto-deploy.

---

## Part 6: Post-Deployment Checklist

### 6.1 Test Your Site
- [ ] Visit `https://blueprintapparel.store`
- [ ] Test email signup form
- [ ] Check that static files load (CSS, images)
- [ ] Test navigation and all pages
- [ ] Verify Stripe is in production mode

### 6.2 Create Superuser (Admin Access)
```bash
# In Render dashboard, go to Shell tab and run:
python manage.py createsuperuser
```

### 6.3 Access Wagtail Admin
- Visit: `https://blueprintapparel.store/admin`
- Login with superuser credentials
- Add/edit content as needed

### 6.4 Monitor Logs
- In Render dashboard: **Logs** tab
- Watch for any errors during first few visits

---

## Troubleshooting

### Issue: "Bad Request (400)" Error
**Solution**: Add your domain to `ALLOWED_HOSTS` in `production.py`

### Issue: Static files not loading
**Solution**:
1. Check that `build.sh` ran successfully
2. Verify `STATIC_ROOT` and `STATIC_URL` in settings
3. Check Render logs for errors during `collectstatic`

### Issue: DNS not resolving
**Solution**:
1. Verify DNS records in GoDaddy
2. Wait for propagation (up to 48 hours)
3. Use `dig` or `nslookup` to check DNS

### Issue: SSL certificate error
**Solution**:
1. Wait a few minutes for Render to provision certificate
2. Ensure both root and www domains are added in Render
3. Check that DNS is fully propagated

### Issue: Database errors
**Solution**:
1. Check that migrations ran in `build.sh`
2. Consider using Render's PostgreSQL instead of SQLite
3. Check environment variables are set correctly

---

## Useful Commands

**Check DNS:**
```bash
dig blueprintapparel.store
nslookup blueprintapparel.store
```

**Test site:**
```bash
curl -I https://blueprintapparel.store
```

**Git deployment:**
```bash
git add .
git commit -m "Update for production"
git push origin master
# Render auto-deploys on push
```

---

## Support Resources

- **Render Docs**: https://render.com/docs
- **GoDaddy DNS Help**: https://www.godaddy.com/help/manage-dns-records-680
- **Django Deployment**: https://docs.djangoproject.com/en/stable/howto/deployment/

---

## Next Steps After Deployment

1. **Set up monitoring** - Use Render's built-in monitoring or integrate services like Sentry
2. **Configure backups** - Set up database backups if using PostgreSQL
3. **Performance optimization** - Consider upgrading to a paid Render plan for better performance
4. **SEO** - Add meta tags, sitemap, Google Analytics
5. **Email marketing** - Connect your email signup to Mailchimp or similar service
