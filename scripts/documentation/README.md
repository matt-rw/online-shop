# Blueprint Apparel - Online Shop

Modern e-commerce website built with Django, Wagtail CMS, and Tailwind CSS.

## 🏪 About

Blueprint Apparel is a Chicago-based clothing brand focused on clean design, versatile pieces, and intentional style. Our debut FOUNDATION collection draws inspiration from Japanese gardens and Korean art, channeling balance and purpose into modern apparel.

## 🚀 Quick Start

### Development
```bash
# Run the development server (Django + Tailwind)
./dev.sh

# Access the site
http://localhost:8000
```

### Deployment
See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for complete deployment instructions.

## 📚 Documentation

All documentation is located in the **[docs/](docs/)** directory:

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Deploy to Render with custom domain
- **[GoDaddy DNS Setup](docs/GODADDY_DNS_SETUP.md)** - Configure DNS (migrating from Shopify)
- **[Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)** - Pre-deployment checklist

## 🛠️ Tech Stack

- **Backend**: Django 5.2, Wagtail 7.0
- **Frontend**: Tailwind CSS, Alpine.js
- **Database**: SQLite (dev), PostgreSQL (production)
- **Payments**: Stripe
- **Hosting**: Render
- **Domain**: GoDaddy

## 📁 Project Structure

```
online-shop/
├── docs/                    # Documentation
├── home/                    # Home app (landing page)
├── shop/                    # Shop app (products, cart)
├── online_shop/             # Project settings
│   └── settings/
│       ├── base.py         # Base settings
│       ├── dev.py          # Development settings
│       └── production.py   # Production settings
├── templates/               # HTML templates
│   ├── base.html           # Base template
│   ├── home/               # Home page templates
│   ├── shop/               # Shop templates
│   └── partials/           # Reusable components
├── static/                  # Static files (images, fonts)
├── theme/                   # Tailwind CSS theme
├── requirements.txt         # Python dependencies
├── build.sh                # Production build script
├── dev.sh                  # Development server script
└── render.yaml             # Render deployment config
```

## 🔑 Environment Variables

Copy `.env` for local development:

```bash
# Stripe (use test keys for development)
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key

# Email (optional for dev)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

See `docs/DEPLOYMENT.md` for production environment variables.

## 🎨 Features

- ✅ Wagtail CMS for content management
- ✅ Tailwind CSS for modern styling
- ✅ Stripe payment integration (ready)
- ✅ Email newsletter signup
- ✅ Responsive design (mobile-first)
- ✅ Smooth scroll animations (AOS)
- ✅ Instagram integration
- 🚧 Shopping cart (coming soon)
- 🚧 Product variants (coming soon)
- 🚧 User accounts (coming soon)

## 📝 License

Proprietary - All rights reserved

## 🔗 Links

- **Website**: https://blueprintapparel.store
- **Instagram**: [@_blueprintapparel](https://instagram.com/_blueprintapparel)
- **Repository**: https://github.com/matt-rw/online-shop

---

For detailed documentation, visit the **[docs/](docs/)** directory.
