#!/usr/bin/env bash
################################################################################
# Production Build Script for Render
################################################################################
# This script runs during deployment on Render to:
# 1. Install Python dependencies
# 2. Collect static files
# 3. Run database migrations
################################################################################

set -o errexit  # Exit on error
set -o pipefail # Exit on pipe failure

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✔ ${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠ ${NC} $1"
}

log_error() {
    echo -e "${RED}✖ ${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

# Start build
log_section "Starting Production Build"
log_info "Build started at $(date '+%Y-%m-%d %H:%M:%S')"
log_info "Python version: $(python --version)"
log_info "Pip version: $(pip --version)"

# Step 1: Install dependencies
log_section "Step 1/4: Installing Python Dependencies"
log_info "Installing packages from requirements.txt..."
if pip install -r requirements.txt --no-cache-dir; then
    log_success "Dependencies installed successfully"
    log_info "Installed packages:"
    pip list | grep -E "(Django|wagtail|gunicorn|stripe|whitenoise)" || true
else
    log_error "Failed to install dependencies"
    exit 1
fi

# Step 2: Build Tailwind CSS
log_section "Step 2/4: Building Tailwind CSS"
log_info "Compiling Tailwind CSS..."
if python manage.py tailwind build; then
    log_success "Tailwind CSS compiled successfully"
else
    log_error "Failed to compile Tailwind CSS"
    exit 1
fi

# Step 3: Collect static files
log_section "Step 3/4: Collecting Static Files"
log_info "Running collectstatic..."
if python manage.py collectstatic --no-input --clear; then
    log_success "Static files collected successfully"
    # Show some stats
    if [ -d "staticfiles" ]; then
        FILE_COUNT=$(find staticfiles -type f | wc -l)
        DIR_SIZE=$(du -sh staticfiles | cut -f1)
        log_info "Total static files: $FILE_COUNT"
        log_info "Total size: $DIR_SIZE"
    fi
else
    log_error "Failed to collect static files"
    exit 1
fi

# Step 4: Run database migrations
log_section "Step 4/4: Running Database Migrations"
log_info "Checking for pending migrations..."
if python manage.py migrate --no-input; then
    log_success "Database migrations completed successfully"
    # Show migration status
    log_info "Migration status:"
    python manage.py showmigrations --plan | tail -n 5 || true
else
    log_error "Failed to run migrations"
    exit 1
fi

# Build complete
log_section "Build Complete"
log_success "Production build finished successfully!"
log_info "Build completed at $(date '+%Y-%m-%d %H:%M:%S')"
log_info "Ready to start application with: gunicorn online_shop.wsgi:application"
echo ""
