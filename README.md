# Blueprint Apparel

Modern e-commerce platform built with Django and Tailwind CSS.

**Live Site**: [blueprnt.store](https://blueprnt.store)

## About

Blueprint Apparel is a Chicago-based clothing brand focused on clean design, versatile pieces, and intentional style. Our debut FOUNDATION collection draws inspiration from Japanese gardens and Korean art, channeling balance and purpose into modern apparel.

## Tech Stack

| Category | Technology |
|----------|------------|
| Backend | Django 4.2 |
| Frontend | Tailwind CSS, Alpine.js |
| Database | SQLite (dev), PostgreSQL (prod) |
| Hosting | Render |
| Payments | Stripe |
| Email | Resend |
| SMS | Twilio |
| Shipping | EasyPost |

## Features

- Product catalog with variants (size, color)
- Shopping cart with session persistence
- Stripe Checkout integration
- Real-time shipping rates
- User accounts (django-allauth)
- Admin dashboard for orders, inventory, and campaigns
- Email & SMS marketing tools
- Responsive mobile-first design

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
./dev.sh

# Access at http://localhost:8000
```

## Environment Variables

Create a `.env` file:

```bash
SECRET_KEY=your-secret-key

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx

# Resend (email)
RESEND_API_KEY=re_xxx

# Twilio (SMS - optional)
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1234567890
```

## Links

- [blueprnt.store](https://blueprnt.store)
- [@_blueprintapparel](https://instagram.com/_blueprintapparel)

## License

Proprietary - All rights reserved
