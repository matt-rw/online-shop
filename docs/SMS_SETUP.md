# SMS Marketing System with Twilio

This document explains how to set up and use the SMS marketing system integrated with Twilio.

## Features

- **SMS Subscriptions**: Users can subscribe via phone number on the homepage
- **Template Management**: Create reusable SMS templates with variable support
- **Automated Triggers**: Automatically send messages on events (new signup, confirmation, etc.)
- **Campaign System**: Schedule and send bulk SMS campaigns
- **Admin Dashboard**: Manage subscribers, templates, campaigns, and view logs
- **Message Logging**: Track all sent messages with delivery status

## Setup Instructions

### 1. Install Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get Twilio Credentials

1. Sign up for a Twilio account at https://www.twilio.com
2. Get your Account SID and Auth Token from the Twilio Console
3. Get a Twilio phone number (or use your existing one)

### 3. Configure Environment Variables

Add these to your `.env` file:

```bash
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Set Up Scheduled Campaign Processing (Optional)

To enable scheduled campaigns, set up a cron job to run every minute:

```bash
* * * * * cd /path/to/online-shop && source venv/bin/activate && python manage.py process_sms_campaigns >> /var/log/sms_campaigns.log 2>&1
```

Or use a task scheduler like Celery, django-q, or django-tasks.

## Usage

### Frontend Subscription Form

Users can now toggle between Email and SMS subscription on the homepage at `/#subscribe`:

- Click the "SMS" tab
- Enter their phone number
- Submit to subscribe

### Admin Dashboard

Access the admin dashboard at `/admin/`:

#### 1. SMS Subscriptions (`/admin/shop/smssubscription/`)

- View all SMS subscribers
- See confirmation and active status
- Export to CSV
- Mark as active/inactive
- Filter by status, source, and date

#### 2. SMS Templates (`/admin/shop/smstemplate/`)

Create reusable message templates:

**Template Variables:**
Use `{variable_name}` in your message. Example:
```
Hi {first_name}! Welcome to Blueprint. Your confirmation code is {code}.
```

**Auto-Trigger Options:**
- `Manual Only`: No automatic sending
- `On New Subscription`: Automatically sent when someone subscribes
- `On Confirmation Request`: Sent when confirmation is requested
- `Scheduled Campaign`: Used only for scheduled campaigns

**Example Welcome Template:**
```
Name: Welcome Message
Type: Welcome Message
Auto Trigger: On New Subscription
Message: Welcome to Blueprint! You're now subscribed to SMS updates. Get early access to drops, exclusive deals, and more. Reply STOP to unsubscribe.
```

#### 3. SMS Campaigns (`/admin/shop/smscampaign/`)

Create and manage SMS marketing campaigns:

**Create a Campaign:**
1. Click "Add SMS Campaign"
2. Enter campaign name
3. Select a template
4. Choose targeting (currently: all active subscribers)
5. Set status:
   - `Draft`: Not sent yet
   - `Scheduled`: Will be sent at scheduled time
6. Optionally set a scheduled time
7. Save

**Send a Campaign:**
- **Immediately**: Select campaign → Actions → "Send selected campaigns now"
- **Scheduled**: Set `scheduled_at` and status to `Scheduled`, then run `process_sms_campaigns` management command

**Campaign Progress:**
View real-time statistics:
- Total recipients
- Sent count
- Failed count
- Progress percentage

#### 4. SMS Logs (`/admin/shop/smslog/`)

View all sent messages:
- Message content
- Recipient phone number
- Status (queued, sent, delivered, failed)
- Twilio SID
- Associated campaign/template
- Error messages (if failed)
- Delivery timestamps

## Management Commands

### Process Scheduled Campaigns

```bash
python manage.py process_sms_campaigns
```

This command:
- Finds campaigns with status='scheduled' and scheduled_at <= now
- Sends them to all targeted subscribers
- Updates campaign progress in real-time
- Logs all messages

## API Reference

### Programmatic Usage

```python
from shop.models import SMSSubscription, SMSTemplate
from shop.utils.twilio_helper import send_sms, send_from_template, trigger_auto_send

# Send a simple SMS
success, log = send_sms(
    phone_number='+1234567890',
    message='Hello from Blueprint!'
)

# Send using a template
template = SMSTemplate.objects.get(name='Welcome Message')
success, log = send_from_template(
    phone_number='+1234567890',
    template=template,
    context={'first_name': 'John'}
)

# Trigger auto-send on subscription
subscription = SMSSubscription.objects.get(phone_number='+1234567890')
trigger_auto_send('on_subscribe', subscription)
```

## Testing

To test without sending real SMS (during development):

1. Check the logs in the admin dashboard
2. Twilio credentials not configured will log warnings instead of sending
3. Use Twilio's test credentials for sandbox testing

## Compliance Notes

- Users can reply STOP to unsubscribe (handled by Twilio)
- All subscription forms include required disclaimers
- Phone numbers are validated and stored in E.164 format
- Inactive subscribers are excluded from campaigns

## Troubleshooting

### SMS not sending

1. Check Twilio credentials in `.env`
2. Verify phone number format (+1234567890)
3. Check SMS logs for error messages
4. Ensure Twilio account has sufficient balance
5. Verify phone number is verified in Twilio (for trial accounts)

### Scheduled campaigns not running

1. Ensure cron job or task scheduler is set up
2. Check that campaign status is 'scheduled'
3. Verify scheduled_at is in the past
4. Check logs for errors

### Template variables not rendering

1. Ensure variables are wrapped in curly braces: `{variable_name}`
2. Pass context dictionary when calling `send_from_template()`
3. Variable names are case-sensitive

## File Structure

```
shop/
├── models/
│   └── sms.py                    # SMS models
├── utils/
│   └── twilio_helper.py          # Twilio integration
├── management/
│   └── commands/
│       └── process_sms_campaigns.py  # Campaign processor
├── views.py                      # SMS subscription view
├── urls.py                       # SMS routes
└── admin.py                      # Admin configuration

templates/
└── home/
    └── home_page.html            # Frontend form with SMS option

requirements.txt                   # Dependencies (includes twilio)
```

## Next Steps

1. Set up your Twilio account and add credentials
2. Run migrations
3. Create your first SMS template in the admin
4. Test subscription on the homepage
5. Create and send your first campaign
