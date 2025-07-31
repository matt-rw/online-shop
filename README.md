# 🛍️ Online Shop

A modern, customizable e-commerce website built using **Wagtail CMS**, **Django**, **Tailwind CSS**, and **Stripe** for payments.

---

## 🚀 Features

- ⚙️ **Django** backend with Wagtail CMS
- 📐 **Tailwind CSS** for responsive frontend styling
- 💳 **Stripe integration** for secure payments
- 🛒 Product pages, cart system, checkout flow
- 🔐 User authentication & admin panel
- 🧩 Modular and extensible architecture

---

## 🧱 Stack

| Layer       | Tech Stack                  |
|-------------|-----------------------------|
| Backend     | Django, Wagtail             |
| Frontend    | Tailwind CSS, Alpine.js     |
| Payments    | Stripe                      |
| Database    | PostgreSQL (or SQLite)      |
| Tooling     | Docker (optional), Poetry   |

---

## 🛠️ Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/matt-rw/online-shop.git
cd online-shop
```

### 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip -r requirements.txt
```

### 2. Run the development server

```bash
python manage.py runserver 0.0.0.0:8000
```

In a separate terminal, start the Tailwind CSS development watcher.

```bash
python manage.py tailwind start
```

