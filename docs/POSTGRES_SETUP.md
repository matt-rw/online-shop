# PostgreSQL Setup Guide for Render

This guide walks you through switching from SQLite to PostgreSQL on Render.

## Why PostgreSQL?

- **SQLite**: Great for development, but limited for production
  - File-based database
  - No concurrent write support
  - Data stored in your web service (lost on redeploy)

- **PostgreSQL**: Industry-standard for production
  - Robust, scalable, and reliable
  - Handles concurrent connections
  - Separate database service (data persists)
  - Better performance for web applications

## Prerequisites

- Render account
- Your Django app already deployed on Render
- Access to Render dashboard

---

## Step 1: Create PostgreSQL Database on Render

1. **Log into Render Dashboard**
   - Go to https://dashboard.render.com

2. **Create New PostgreSQL Database**
   - Click **"New +"** button (top right)
   - Select **"PostgreSQL"**

3. **Configure Database**
   - **Name**: `online-shop-db` (or your preferred name)
   - **Database**: `online_shop` (auto-generated, you can customize)
   - **User**: `online_shop_user` (auto-generated)
   - **Region**: Same region as your web service (for best performance)
   - **PostgreSQL Version**: Latest stable (e.g., 16)
   - **Plan**: Free tier is fine to start

4. **Create Database**
   - Click **"Create Database"**
   - Wait 1-2 minutes for provisioning

5. **Note the Connection Details**
   - After creation, you'll see:
     - **Internal Database URL** (use this one - it's faster and free)
     - External Database URL (for external connections)
   - Copy the **Internal Database URL** - it looks like:
     ```
     postgresql://user:password@dpg-xxxxx/database_name
     ```

---

## Step 2: Connect Database to Your Web Service

### Option A: Using Environment Variables (Recommended)

1. **Go to Your Web Service**
   - Click on your web service (e.g., "online-shop")

2. **Navigate to Environment**
   - Click **"Environment"** in left sidebar

3. **Add DATABASE_URL**
   - Click **"Add Environment Variable"**
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the Internal Database URL from Step 1
   - Click **"Save Changes"**

### Option B: Link Database Directly

1. **Go to Your Web Service**
   - Click on your web service

2. **Navigate to Environment**
   - Scroll to **"Environment Variables"** section

3. **Add from Database**
   - Click **"Add from Database"**
   - Select your PostgreSQL database
   - Render automatically adds `DATABASE_URL`

---

## Step 3: Run Database Migrations

Your app needs to create tables in the new PostgreSQL database.

### Automatic (On Next Deploy)

The migrations will run automatically on your next deploy because your `render.yaml` includes:

```yaml
buildCommand: "./build.sh"
```

And `build.sh` contains:

```bash
python manage.py migrate --noinput
```

### Manual (Run Now)

If you want to migrate immediately without waiting for a deploy:

1. **Go to Your Web Service**
   - Click on your service in Render dashboard

2. **Open Shell**
   - Click **"Shell"** tab
   - This opens a terminal in your running container

3. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create Superuser** (if needed)
   ```bash
   python manage.py createsuperuser
   ```

---

## Step 4: Verify the Switch

1. **Check Logs**
   - Go to **"Logs"** tab in your web service
   - Look for successful migration messages:
     ```
     Running migrations:
       Applying contenttypes.0001_initial... OK
       Applying auth.0001_initial... OK
       ...
     ```

2. **Test Your Site**
   - Visit your live site
   - Try logging into admin: `https://yoursite.com/admin`
   - If admin doesn't work, you need to create a superuser (see Step 3)

3. **Check Database Connection**
   - In Render Shell, run:
     ```bash
     python manage.py dbshell
     ```
   - If it connects to PostgreSQL, you're good!
   - Type `\q` to exit

---

## Step 5: Migrate Existing Data (If Needed)

If you have existing data in SQLite that you want to keep:

### Export from SQLite

1. **Locally**, export data:
   ```bash
   python manage.py dumpdata --exclude auth.permission --exclude contenttypes > data.json
   ```

2. **Upload** `data.json` to your repository

### Import to PostgreSQL

1. **In Render Shell**, load data:
   ```bash
   python manage.py loaddata data.json
   ```

**Note**: For a new site without user data, you can skip this step.

---

## What's Changed in Your Code

The following files were updated to support PostgreSQL:

### `online_shop/settings/production.py`

```python
import dj_database_url

# Database - PostgreSQL for production
DATABASE_URL = get_env_variable('DATABASE_URL', None)

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
```

**What this does**:
- Reads `DATABASE_URL` from environment variables
- Uses `dj-database-url` to parse the connection string
- Sets `conn_max_age=600` for connection pooling (better performance)
- Enables `conn_health_checks=True` to automatically reconnect if connection drops

### `requirements.txt`

Added two new packages:
- `psycopg2-binary` - PostgreSQL database adapter for Python
- `dj-database-url` - Parses DATABASE_URL into Django settings

---

## Local Development

**Important**: Your local development still uses SQLite, which is perfect for development.

- **Local**: Uses SQLite (defined in `online_shop/settings/dev.py`)
- **Production**: Uses PostgreSQL (defined in `online_shop/settings/production.py`)

This is controlled by the `DJANGO_SETTINGS_MODULE` environment variable:
- Local: `DJANGO_SETTINGS_MODULE=online_shop.settings.dev`
- Render: `DJANGO_SETTINGS_MODULE=online_shop.settings.production`

---

## Troubleshooting

### "Could not connect to server"

**Problem**: Web service can't connect to database

**Solutions**:
1. Check `DATABASE_URL` is set correctly in environment variables
2. Verify database and web service are in the same region
3. Use **Internal Database URL**, not External
4. Check database status - it should be "Available"

### "relation does not exist"

**Problem**: Tables haven't been created

**Solution**: Run migrations
```bash
python manage.py migrate
```

### "FATAL: password authentication failed"

**Problem**: Wrong database credentials

**Solutions**:
1. Copy the Internal Database URL again from database dashboard
2. Update `DATABASE_URL` environment variable
3. Restart web service

### "Too many connections"

**Problem**: Free tier has limited connections

**Solutions**:
1. Add `conn_max_age=600` to database config (already done)
2. Upgrade to paid plan for more connections
3. Close unused database connections

### Lost admin access after migration

**Problem**: Superuser wasn't created in PostgreSQL

**Solution**: Create a new superuser
```bash
python manage.py createsuperuser
```

---

## Monitoring Your Database

### View Database Dashboard

1. Click on your PostgreSQL database in Render
2. You'll see:
   - **Connection count** - How many active connections
   - **Database size** - How much storage used
   - **Connections** - Recent connection activity

### Free Tier Limits

- **Storage**: 1 GB
- **Connections**: 97 concurrent
- **Retention**: 90 days (database deleted if inactive)

**Tip**: Render's free tier is great for getting started. Upgrade to paid if you need more.

---

## Next Steps

After PostgreSQL is working:

1. **Set up backups** - Render handles this automatically for paid plans
2. **Monitor performance** - Check database metrics in Render dashboard
3. **Optimize queries** - Use Django Debug Toolbar locally to find slow queries
4. **Consider Redis** - For caching and session storage (future enhancement)

---

## Quick Reference

| Task | Command |
|------|---------|
| Run migrations | `python manage.py migrate` |
| Create superuser | `python manage.py createsuperuser` |
| Access database shell | `python manage.py dbshell` |
| Export data | `python manage.py dumpdata > data.json` |
| Import data | `python manage.py loaddata data.json` |
| Check database | `python manage.py check --database default` |

---

## Support

- **Render Docs**: https://render.com/docs/databases
- **Django Database Docs**: https://docs.djangoproject.com/en/stable/ref/databases/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

**Questions?** Check the Render community forum or your developer.
