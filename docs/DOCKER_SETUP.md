# Docker Setup Guide

This guide explains how to use Docker for local development with the Blueprint Apparel project.

## 📋 Overview

**Current Production Deployment:** Native Python on Render (no Docker)
- Uses `build.sh` and `render.yaml`
- Simpler and faster for our use case

**Docker Usage:** Local development only
- Provides PostgreSQL database locally (matches production)
- Isolated environment
- Easy setup for new developers

---

## 🐳 What's Included

### Files:
- **Dockerfile** - Defines the application container
- **docker-compose.yml** - Orchestrates services (Django + PostgreSQL)

### Services:
- **web** - Django/Wagtail application (port 8000)
- **db** - PostgreSQL 15 database (port 5432)

---

## 🚀 Quick Start

### 1. Prerequisites
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Docker Compose comes included with Docker Desktop

### 2. Start Development Environment

```bash
# Start all services (first time will build images)
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
```

### 3. Access the Application

- **Website**: http://localhost:8000
- **Admin**: http://localhost:8000/admin
- **Wagtail Admin**: http://localhost:8000/admin

### 4. Create Superuser

```bash
# In a new terminal, run:
docker-compose exec web python manage.py createsuperuser
```

### 5. Stop Services

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

---

## 🛠️ Common Tasks

### Run Migrations
```bash
docker-compose exec web python manage.py migrate
```

### Create Migrations
```bash
docker-compose exec web python manage.py makemigrations
```

### Collect Static Files
```bash
docker-compose exec web python manage.py collectstatic --no-input
```

### Shell Access
```bash
# Django shell
docker-compose exec web python manage.py shell

# Bash shell in container
docker-compose exec web bash

# PostgreSQL shell
docker-compose exec db psql -U postgres -d online_shop
```

### Run Tests
```bash
docker-compose exec web python manage.py test
```

### Rebuild Containers
```bash
# After changing Dockerfile or requirements.txt
docker-compose build

# Or rebuild and start
docker-compose up --build
```

---

## 📁 Volumes

Docker Compose creates persistent volumes for:
- **postgres_data** - Database data (persists between restarts)
- **static_volume** - Collected static files
- **media_volume** - User-uploaded media files

### View Volumes
```bash
docker volume ls
```

### Remove All Volumes (Careful!)
```bash
docker-compose down -v
```

---

## 🔧 Configuration

### Environment Variables

Edit `docker-compose.yml` to change environment variables:

```yaml
environment:
  STRIPE_SECRET_KEY: sk_test_your_key_here
  STRIPE_PUBLISHABLE_KEY: pk_test_your_key_here
  EMAIL_HOST_USER: your-email@gmail.com
```

### Database Connection

The web service connects to PostgreSQL using:
```
DATABASE_URL: postgres://postgres:postgres@db:5432/online_shop
```

To use this in your settings, install `dj-database-url`:
```bash
pip install dj-database-url
```

Then in settings:
```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}
```

---

## 🆚 Docker vs Native Development

### Use Docker When:
- ✅ You want PostgreSQL locally (matches production)
- ✅ New team members need quick setup
- ✅ Testing production-like environment
- ✅ Working with system dependencies

### Use Native Python When:
- ✅ Faster iteration (no container rebuild)
- ✅ Simpler debugging
- ✅ Direct file access
- ✅ Lighter resource usage

**Recommendation:** Start with native (`./dev.sh`), use Docker when you need PostgreSQL or production parity.

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Access at localhost:8001
```

### Database Connection Errors
```bash
# Check if database is healthy
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Permission Errors
```bash
# Fix ownership (Linux/Mac)
sudo chown -R $USER:$USER .
```

### Container Won't Start
```bash
# View detailed logs
docker-compose logs web

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Changes Not Reflecting
```bash
# For code changes: just save (volume mounted)
# For requirements.txt: rebuild
docker-compose build web
docker-compose up
```

---

## 📝 Notes

- **SQLite vs PostgreSQL**: Docker setup uses PostgreSQL, matching production. Native development uses SQLite for simplicity.
- **Performance**: Docker on Mac/Windows uses virtualization, which may be slower than native.
- **Data Persistence**: Database data persists in Docker volumes even after stopping containers.
- **Hot Reload**: Code changes are reflected immediately (no restart needed) because of volume mounting.

---

## 🔗 Resources

- **Docker Documentation**: https://docs.docker.com
- **Docker Compose**: https://docs.docker.com/compose
- **PostgreSQL Image**: https://hub.docker.com/_/postgres
- **Django on Docker**: https://docs.docker.com/samples/django

---

Last Updated: January 6, 2025
