# E-commerce Implementation Guide

## ✅ Completed Backend Implementation

### 1. User Authentication (django-allauth)
- **Installed**: django-allauth with email-based authentication
- **Features**: Email verification, password reset, social auth ready
- **URLs**: `/accounts/login/`, `/accounts/signup/`, `/accounts/logout/`

### 2. User Profile & Saved Addresses
- **Models**: `UserProfile`, `SavedAddress`
- **Features**: Multiple saved addresses, default shipping/billing
- **Auto-created**: Profile created automatically when user signs up

### 3. Cart Management
- **Models**: `Cart`, `CartItem` (already existed)
- **Utils**: `/shop/cart_utils.py` with functions:
  - `get_or_create_cart()` - Works for both logged-in and anonymous users
  - `add_to_cart()` - Add items with quantity
  - `update_cart_item_quantity()` - Update or remove items
  - `merge_carts()` - Automatically merges anonymous cart when user logs in
  - `get_cart_total()` - Calculate cart total
  - `get_cart_count()` - Get total item count

### 4. Cart Views & URLs
**File**: `/shop/cart_views.py`

| URL | View | Description |
|-----|------|-------------|
| `/shop/cart/` | `cart_view` | Display shopping cart |
| `/shop/cart/add/` | `add_to_cart_view` | Add item to cart (POST) |
| `/shop/cart/update/<id>/` | `update_cart_item_view` | Update quantity (POST) |
| `/shop/cart/remove/<id>/` | `remove_from_cart_view` | Remove item (POST) |
| `/shop/checkout/` | `checkout_view` | Checkout page |
| `/shop/checkout/create-session/` | `create_checkout_session` | Create Stripe session |
| `/shop/checkout/success/` | `checkout_success_view` | Order confirmation |

### 5. Stripe Integration
**Stripe Checkout Flow**:
1. User clicks "Checkout" → redirected to `/shop/checkout/`
2. User enters shipping info → clicks "Pay Now"
3. Creates Stripe Checkout Session → redirects to Stripe hosted checkout
4. After payment → redirects back to `/shop/checkout/success/`
5. Webhook confirms payment → order marked as PAID

**Webhook Handler**: `/shop/webhooks.py`
- Endpoint: `/shop/webhook/stripe/`
- Handles: `checkout.session.completed`, `payment_intent.succeeded`, `payment_intent.payment_failed`

### 6. Context Processor
**File**: `/shop/context_processors.py`
- Makes `cart_count` and `cart_total` available in ALL templates
- Use in navbar: `{{ cart_count }}` items

---

## 🚧 TODO: Templates to Create

### Priority 1: Essential Templates
1. **`templates/shop/checkout.html`** - Checkout page with address form
2. **`templates/shop/checkout_success.html`** - Order confirmation
3. **Update `templates/shop/product_page.html`** - Add variant selector and "Add to Cart" button

### Priority 2: Authentication Templates
Create in `templates/account/` (allauth templates):
4. **`login.html`** - Login form
5. **`signup.html`** - Registration form
6. **`password_reset.html`** - Password reset

### Priority 3: User Account
7. **`templates/shop/profile.html`** - User profile page
8. **`templates/shop/order_history.html`** - Past orders
9. **`templates/shop/saved_addresses.html`** - Manage saved addresses

---

## 🔧 Configuration Needed

### 1. Stripe Configuration
Add to your `.env` file (already have keys, but add webhook secret):
```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # Get this from Stripe Dashboard → Webhooks
```

### 2. Stripe Webhook Setup
1. Go to https://dashboard.stripe.com/test/webhooks
2. Click "Add endpoint"
3. URL: `https://blueprintapparel.store/shop/webhook/stripe/`
4. Events to send:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
5. Copy the "Signing secret" (whsec_...) to your `.env` as `STRIPE_WEBHOOK_SECRET`

### 3. Email Configuration
Already configured in `base.py` - just ensure these are set in production:
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

---

## 📝 Template Examples

### Add to Cart Form (for product pages)
```html
<form method="post" action="{% url 'shop:add_to_cart' %}">
    {% csrf_token %}

    <!-- Variant selection (size, color) -->
    <select name="variant_id" required>
        {% for variant in page.product.variants.all %}
            <option value="{{ variant.id }}">
                {{ variant.size }} - {{ variant.color }} - ${{ variant.price }}
            </option>
        {% endfor %}
    </select>

    <!-- Quantity -->
    <input type="number" name="quantity" value="1" min="1">

    <button type="submit">Add to Cart</button>
</form>
```

### Cart Count in Navbar
```html
<a href="{% url 'shop:cart' %}">
    Cart ({{ cart_count }})
</a>
```

---

## 🧪 Testing Checklist

### Local Testing (Test Mode Stripe)
- [ ] Add product to cart as anonymous user
- [ ] Update cart quantities
- [ ] Remove items from cart
- [ ] Create account while items in cart (cart should persist)
- [ ] Proceed to checkout
- [ ] Complete test payment with Stripe test card: `4242 4242 4242 4242`
- [ ] Verify order appears in Django admin
- [ ] Check order status updates to PAID

### Stripe Test Cards
- **Success**: 4242 4242 4242 4242
- **Decline**: 4000 0000 0000 0002
- **3D Secure**: 4000 0027 6000 3184

### Webhook Testing (Local)
1. Install Stripe CLI: `brew install stripe/stripe-cli/stripe`
2. Login: `stripe login`
3. Forward webhooks: `stripe listen --forward-to localhost:8000/shop/webhook/stripe/`
4. Test: Make a test purchase
5. Check logs: Should see webhook events

---

## 🚀 Next Steps

1. **Create Templates** (see TODO above)
2. **Test Locally** with Stripe test mode
3. **Add Discount Codes** (optional - can be added later)
4. **Add Email Notifications**:
   - Order confirmation
   - Shipping notifications
   - Password reset (allauth handles this)
5. **Add Order Management** for admin
6. **Add Product Images** to cart/checkout

---

## 📦 Database Migrations

All migrations have been created and run:
- `shop/migrations/0005_userprofile_savedaddress.py` - User profiles

To apply in production:
```bash
python manage.py migrate
```

---

## 🔒 Security Notes

1. **CSRF Protection**: All POST endpoints require CSRF token (except webhook)
2. **Webhook Verification**: Stripe signature verification enabled
3. **User Isolation**: Cart operations verify user ownership
4. **Email Verification**: Required for new accounts (allauth)
5. **HTTPS**: Required in production (already configured)

---

## 💡 Tips

### Cart Persistence
- Anonymous users: Cart stored by session key
- Logged-in users: Cart stored by user FK
- On login: Carts are automatically merged

### Order Fulfillment Workflow
1. Order created with status `AWAITING_PAYMENT`
2. Stripe processes payment
3. Webhook updates order to `PAID`
4. Admin fulfills order → update to `SHIPPED`
5. Mark as `FULFILLED` when delivered

### Discount Codes (Future)
Create a `DiscountCode` model with:
- `code` (unique)
- `discount_type` (percentage or fixed)
- `discount_value`
- `valid_from`, `valid_to`
- `max_uses`, `current_uses`

Apply in checkout before creating Stripe session.

---

**Status**: Backend 100% complete, templates 20% complete
**Next**: Create checkout and authentication templates
