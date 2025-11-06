# Pre-Deployment Checklist

All code updates have been made and are ready for deployment to Render.

## ✅ Code Changes Completed

### 1. `.gitignore` Updated
- Added comprehensive Python/Django ignores
- Excludes virtual environments, databases, and sensitive files
- Ignores `staticfiles/` and `media/` directories
- IDE and OS-specific files excluded

### 2. `production.py` Enhanced
- ✅ `ALLOWED_HOSTS` includes:
  - `.onrender.com`
  - `blueprintapparel.store`
  - `www.blueprintapparel.store`
- ✅ `WAGTAILADMIN_BASE_URL` set to production domain
- ✅ WhiteNoise middleware configured for efficient static file serving
- ✅ Compressed manifest storage for optimal performance
- ✅ All security settings enabled (SSL, HSTS, secure cookies)

### 3. `render.yaml` Created
- Optional infrastructure-as-code file
- Pre-configured for Python 3.8
- Includes build and start commands
- Environment variable templates

### 4. Deployment Documentation
- ✅ `DEPLOYMENT.md` - Complete deployment guide
- ✅ `GODADDY_DNS_SETUP.md` - DNS configuration guide
- ✅ `DEPLOYMENT_CHECKLIST.md` - This file!

---

## 📋 Before You Deploy

### Step 1: Verify Local Environment
```bash
# Make sure you're in the project directory
cd /home/matt/projects/online-shop

# Check that all files are present
ls -la

# Test that the dev server still works
./dev.sh
```

### Step 2: Commit and Push to GitHub
```bash
# Stage all changes
git add .

# Commit with descriptive message
git commit -m "Production ready: Add deployment configs and update settings"

# Push to GitHub
git push origin master
```

---

## 🚀 Deployment Steps (Quick Reference)

### 1. Deploy on Render
1. Go to https://render.com
2. Sign up/login (use GitHub account)
3. Create new Web Service
4. Connect repository: `matt-rw/online-shop`
5. Configure:
   - **Name**: `blueprint-apparel`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn online_shop.wsgi:application`
6. Add environment variables (see DEPLOYMENT.md)
7. Click "Create Web Service"
8. Wait for deployment (~5-10 minutes)
9. Note your Render URL: `https://blueprint-apparel.onrender.com`

### 2. Configure GoDaddy DNS
1. Login to GoDaddy
2. Navigate to Domain → DNS Settings
3. **Delete Shopify DNS records**:
   - Remove CNAME to `shops.myshopify.com`
   - Remove A records to Shopify IPs
4. **Add Render DNS records**:
   - A record: `@` → `216.24.57.1`
   - CNAME: `www` → `blueprint-apparel.onrender.com`
5. Wait for DNS propagation (15 mins - 2 hours)

### 3. Add Custom Domain in Render
1. In Render dashboard → Settings → Custom Domains
2. Add `blueprintapparel.store`
3. Add `www.blueprintapparel.store`
4. Wait for SSL certificate provisioning (~5 minutes)

### 4. Test Your Site
1. Visit `https://blueprintapparel.store`
2. Check all pages load correctly
3. Test email signup form
4. Verify static files (images, CSS) load
5. Check SSL certificate (padlock icon in browser)

---

## 🔑 Environment Variables to Set in Render

**Required:**
```
DJANGO_SETTINGS_MODULE=online_shop.settings.production
PYTHON_VERSION=3.8.0
SECRET_KEY=[Generate in Render]
DEBUG=False
```

**Stripe (Production Keys):**
```
STRIPE_SECRET_KEY=sk_live_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_key_here
```

**Email (SMTP):**
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

---

## ✨ Post-Deployment Tasks

### Create Superuser
In Render Shell:
```bash
python manage.py createsuperuser
```

### Access Admin Panel
- Wagtail: `https://blueprintapparel.store/admin`
- Django: `https://blueprintapparel.store/django-admin` (if needed)

### Monitor Logs
- Check Render dashboard → Logs tab
- Watch for any errors during first visits

---

## 🆘 Common Issues & Quick Fixes

### "Bad Request (400)"
→ Domain not in `ALLOWED_HOSTS` (already fixed!)

### Static files not loading
→ Run in Render Shell: `python manage.py collectstatic --no-input`

### DNS not resolving
→ Wait longer, check https://dnschecker.org

### SSL certificate error
→ Wait 5-10 minutes for Render to provision certificate

---

## 📚 Full Documentation

For detailed instructions, see:
- **DEPLOYMENT.md** - Complete deployment guide
- **GODADDY_DNS_SETUP.md** - DNS configuration details

---

## 🎯 You're Ready!

All code changes are complete. Follow the steps above to deploy your site to production.

**Estimated total time**: 30-60 minutes
- Render deployment: 10-15 minutes
- DNS configuration: 5 minutes
- DNS propagation: 15 mins - 2 hours
- Testing: 10 minutes

Good luck! 🚀
