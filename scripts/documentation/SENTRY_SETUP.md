# Sentry Error Monitoring Setup

## What is Sentry?

Sentry automatically captures errors in production and sends you instant alerts with full stack traces, user context, and environment details.

**FREE Tier**: 5,000 errors/month

---

## Setup Instructions (5 minutes)

### Step 1: Create Sentry Account

1. Go to https://sentry.io/signup/
2. Sign up (free tier)
3. Create a new project:
   - Platform: **Django**
   - Project name: **blueprint-apparel**

### Step 2: Get Your DSN

After creating the project, Sentry will show you a **DSN** (Data Source Name).

It looks like:
```
https://abc123def456@o123456.ingest.sentry.io/7891011
```

**Copy this DSN** - you'll need it next.

### Step 3: Add DSN to Render

1. Go to your Render dashboard
2. Click on your web service (**blueprint-apparel**)
3. Go to **Environment** tab
4. Click **Add Environment Variable**
   - Key: `SENTRY_DSN`
   - Value: (paste the DSN you copied)
5. Click **Save Changes**

Render will automatically redeploy with Sentry enabled.

---

## How It Works

### Automatic Error Capture

Sentry automatically captures:

#### 1. Python Exceptions
```python
# This error will be sent to Sentry
def broken_view(request):
    user = User.objects.get(id=999999)  # DoesNotExist error
    return render(request, 'page.html')
```

**Sentry captures:**
- Full stack trace
- Request URL and method
- User (if logged in)
- Server environment
- Time of error

#### 2. Database Errors
```python
# SQL errors automatically captured
Product.objects.filter(invalid_field=123)
```

#### 3. Template Errors
```django
<!-- Missing variable errors -->
{{ product.nonexistent_field }}
```

#### 4. Integration Errors
```python
# Stripe API failures
stripe.PaymentIntent.create(...)  # If this fails, Sentry knows
```

---

## Viewing Errors

### In Sentry Dashboard

1. Go to https://sentry.io/
2. Click your project (**blueprint-apparel**)
3. See all errors in real-time

### Email/Slack Alerts

**Set up alerts:**

1. In Sentry project → **Alerts**
2. Create alert rule:
   - **When**: An event is first seen
   - **Then**: Send notification via Email/Slack
3. Save

Now you get instant notifications when errors happen!

---

## Testing Sentry

### Test That It's Working

Add a test endpoint (temporary):

**File:** `shop/views.py`

```python
def test_sentry(request):
    """Test endpoint to verify Sentry is working."""
    division_by_zero = 1 / 0  # This will trigger an error
    return HttpResponse("This won't be reached")
```

**File:** `shop/urls.py`

```python
urlpatterns = [
    # ... existing paths
    path('test-sentry/', views.test_sentry, name='test_sentry'),  # REMOVE AFTER TESTING
]
```

**Test it:**
1. Deploy to Render
2. Visit: `https://blueprintapparel.store/shop/test-sentry/`
3. You'll see a 500 error
4. Check Sentry dashboard - error should appear within seconds!
5. **Remove the test endpoint after confirming it works**

---

## What Errors Are Captured

### ✅ Captured Automatically

- **500 errors** (server errors)
- **Uncaught exceptions**
- **Database errors**
- **Template rendering errors**
- **API integration failures** (Stripe, Twilio, etc.)

### ❌ Not Captured (by default)

- **404 errors** (not found - too noisy)
- **400 errors** (bad request)
- **Validation errors** (expected user errors)

### Custom Error Capture

You can manually capture specific events:

```python
import sentry_sdk

# Capture a custom error
try:
    send_sms(phone_number, message)
except TwilioException as e:
    sentry_sdk.capture_exception(e)
    # Handle gracefully for user
    messages.error(request, "SMS failed to send")
```

---

## Privacy & Security

### PII (Personal Identifiable Information)

Our config has `send_default_pii=False`, which means:

**NOT sent to Sentry:**
- Passwords
- Credit card numbers
- Email addresses (unless in error message)
- Phone numbers (unless in error message)

**Sent to Sentry:**
- Error message
- Stack trace
- Request URL and method
- Server environment (Python version, Django version, etc.)
- User ID (if logged in, but NOT email/username)

### Scrubbing Sensitive Data

If an error message contains sensitive data, Sentry automatically scrubs:
- `password`
- `secret`
- `api_key`
- `token`
- `credit_card`

Example:
```
Before: "Stripe error with key sk_live_abc123"
After:  "Stripe error with key [Filtered]"
```

---

## Performance Monitoring (Optional)

Sentry also tracks slow requests:

```python
# In production.py (already configured)
traces_sample_rate=0.1  # Monitor 10% of requests
```

**What it shows:**
- Slow database queries
- Slow external API calls (Stripe, Twilio)
- Page load times
- Bottlenecks in your code

**View in Sentry:**
1. Project → **Performance**
2. See slowest transactions
3. Optimize the slow ones!

---

## Cost & Limits

### FREE Tier

- **5,000 errors/month**
- **10,000 performance transactions/month**
- **90 days data retention**
- **Unlimited projects**

### What If You Exceed?

- Sentry stops capturing new errors
- No charges (free tier doesn't auto-upgrade)
- Upgrade to Team plan if needed ($26/month)

### Monitoring Usage

1. Sentry dashboard → **Stats**
2. See errors/month
3. Adjust sample rates if needed

---

## Alerts Configuration

### Recommended Alerts

#### 1. First-Time Errors
**When**: New error first seen
**Action**: Email you immediately
**Why**: New bugs after deployment

#### 2. High Frequency Errors
**When**: Error happens 100+ times in 1 hour
**Action**: Email + Slack
**Why**: Critical issue affecting many users

#### 3. Slow Transactions
**When**: Page takes >3 seconds
**Action**: Create issue
**Why**: Performance degradation

### Setting Up Alerts

1. Sentry → **Alerts** → **Create Alert**
2. Choose conditions
3. Choose actions (Email, Slack, Webhook)
4. Save

---

## Integration with Slack (Optional)

Get errors in Slack:

1. Sentry → **Settings** → **Integrations**
2. Find **Slack** → **Add to Slack**
3. Choose channel (e.g., `#errors`)
4. Configure alert rules to post to Slack

Now errors appear in Slack instantly!

---

## Best Practices

### 1. Set Up Alerts Immediately
Don't just capture errors - **get notified**!

### 2. Check Sentry Daily
Make it part of your routine:
- Morning: Check for overnight errors
- After deployment: Watch for 30 minutes

### 3. Fix Errors Quickly
- Mark as "Resolved" when fixed
- Add notes on how you fixed it
- Link to PR/commit that fixed it

### 4. Use Releases
Sentry tracks which git commit broke things:

```python
# In production.py (already configured)
release=os.environ.get('RENDER_GIT_COMMIT', 'unknown')[:7]
```

**Benefit**: See exactly which deploy introduced the bug!

### 5. Create Issues from Errors
Link Sentry to GitHub:
1. Sentry → **Settings** → **Integrations** → **GitHub**
2. Connect your repo
3. Click "Create Issue" on any Sentry error
4. Automatically creates GitHub issue with full context

---

## Troubleshooting

### Sentry Not Capturing Errors

**Check:**

1. **DSN set in Render?**
   ```bash
   # In Render dashboard Environment tab
   SENTRY_DSN should be set
   ```

2. **Sentry initialized in production?**
   ```python
   # Only runs in production when SENTRY_DSN is set
   # Check logs for: "Sentry initialized"
   ```

3. **Error actually happening?**
   - Test with `/shop/test-sentry/` endpoint
   - Check Django logs

### Too Many Errors

If you're getting flooded:

1. **Ignore noisy errors:**
   - Sentry → Error → **Ignore**
   - Or set ignore rules

2. **Reduce sample rate:**
   ```python
   # In production.py
   traces_sample_rate=0.05  # 5% instead of 10%
   ```

---

## Summary

✅ **Set up in production.py** (already done)
⏳ **Add SENTRY_DSN to Render environment**
⏳ **Set up email/Slack alerts**
⏳ **Test with test endpoint**
⏳ **Remove test endpoint**

**Time to set up**: 5 minutes
**Time saved**: Hours of debugging!

---

## Next Steps

1. Create Sentry account at https://sentry.io/signup/
2. Get your DSN
3. Add to Render environment as `SENTRY_DSN`
4. Deploy
5. Check Sentry dashboard - you should see "Waiting for events..."
6. Test with `/shop/test-sentry/` endpoint
7. Set up alerts

**You'll know it's working when you see errors appear in Sentry dashboard!**
