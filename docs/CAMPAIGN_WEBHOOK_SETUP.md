# Campaign Webhook Setup Guide

This guide explains how to set up automatic campaign processing for your Blueprint Apparel store.

## Overview

The campaign system supports two modes:

1. **Development Mode (DEBUG=True)**: Campaigns process automatically every minute using a background scheduler
2. **Production Mode (DEBUG=False)**: Uses webhook + free external cron service (no Celery Beat or paid workers needed)

### Development Mode (Automatic)

When `DEBUG=True` in your settings, the app automatically starts a background scheduler that processes campaigns every minute. No setup required - just create a campaign and it will send automatically when the scheduled time arrives.

You'll see this message in your console when the server starts:
```
Campaign scheduler started (DEBUG mode) - campaigns will process every minute
```

### Production Mode (Webhook + Cron)

In production, a free external cron service calls your webhook endpoint every minute to process any campaigns that are ready to send.

## Setup Steps

### 1. Add Webhook Secret to Render Environment Variables

Your webhook endpoint is secured with a secret token. You need to add this to your Render environment variables.

1. Go to your Render dashboard: https://dashboard.render.com
2. Select your web service (Blueprint Apparel)
3. Click on "Environment" in the left sidebar
4. Click "Add Environment Variable"
5. Add the following:
   - **Key**: `CAMPAIGN_WEBHOOK_SECRET`
   - **Value**: `mJbSL3EnFTzVtKY8Sy_2qLROuXV-SzgCmympQBh46h8`
6. Click "Save Changes"
7. Your service will automatically redeploy

### 2. Set Up Free Cron Job on cron-job.org

We'll use cron-job.org (free tier) to call your webhook every minute.

1. **Create an account** at https://cron-job.org/en/signup/
   - The free tier allows up to 50 cron jobs
   - No credit card required

2. **Create a new cron job**:
   - Click "Create Cron Job" in your dashboard

3. **Configure the cron job**:
   - **Title**: `Blueprint Apparel - Process Campaigns`
   - **URL**: `https://your-app-name.onrender.com/shop/campaigns/process/?secret=mJbSL3EnFTzVtKY8Sy_2qLROuXV-SzgCmympQBh46h8`
     - Replace `your-app-name` with your actual Render app name
   - **Execution schedule**:
     - Select "Every minute" from the dropdown
     - Or use custom: `* * * * *`
   - **Request method**: GET (default)
   - **Save responses**: Enabled (optional, helps with debugging)

4. **Enable the cron job**:
   - Make sure the "Enabled" toggle is ON
   - Click "Create"

### 3. Verify Setup

#### Test the webhook manually:

```bash
# Replace YOUR_DOMAIN with your actual Render domain
curl "https://your-app-name.onrender.com/shop/campaigns/process/?secret=mJbSL3EnFTzVtKY8Sy_2qLROuXV-SzgCmympQBh46h8"
```

You should see a JSON response like:

```json
{
  "status": "success",
  "results": {
    "timestamp": "2024-11-19T18:30:00.000000+00:00",
    "email_campaigns": {
      "processed": 0,
      "sent": 0,
      "failed": 0,
      "errors": []
    },
    "sms_campaigns": {
      "processed": 0,
      "sent": 0,
      "failed": 0,
      "errors": []
    }
  }
}
```

#### Check cron job execution:

1. Go to your cron-job.org dashboard
2. Click on your "Process Campaigns" job
3. View the "Execution history" tab
4. Recent executions should show status 200 (success)

## How It Works

1. **Campaign Creation**: Admin creates email/SMS campaigns via the admin dashboard
2. **Scheduling**: Admin sets a scheduled time for the campaign
3. **Automatic Processing**:
   - Every minute, cron-job.org calls your webhook
   - The webhook checks for campaigns where `scheduled_at <= now`
   - Campaigns with status "scheduled" are sent automatically
   - Campaign status is updated to "sent" or "failed"
4. **Results**: The webhook returns statistics about what was processed

## Security

- The webhook requires a secret token to prevent unauthorized access
- The secret is 43 characters long and cryptographically secure
- Only requests with the correct secret will be processed
- Failed authentication attempts are logged

## Troubleshooting

### Campaigns not sending

1. **Check cron job is running**:
   - Visit cron-job.org dashboard
   - Verify job is enabled
   - Check execution history for errors

2. **Check webhook secret**:
   - Verify `CAMPAIGN_WEBHOOK_SECRET` is set in Render environment variables
   - Verify the secret in your cron job URL matches exactly

3. **Check campaign status**:
   - In admin dashboard, verify campaign status is "scheduled"
   - Verify `scheduled_at` time is in the past
   - Check campaign has recipients (subscribers)

4. **View logs in Render**:
   - Go to Render dashboard
   - Click "Logs" tab
   - Look for webhook execution logs
   - Check for any error messages

### 401 Unauthorized error

- The secret token doesn't match
- Check the URL in cron-job.org matches the secret in your environment variables

### 500 Server error

- `CAMPAIGN_WEBHOOK_SECRET` is not set in environment variables
- Check Render logs for specific error details

## Alternative Free Cron Services

If cron-job.org doesn't work for you, here are alternatives:

1. **EasyCron** (https://www.easycron.com/)
   - Free tier: 1 cron job
   - Good for single webhook

2. **cron-job.org** (https://cron-job.org/) - RECOMMENDED
   - Free tier: 50 cron jobs
   - Most reliable

3. **GitHub Actions** (if you're comfortable with YAML)
   - Completely free
   - Runs from your GitHub repository
   - Requires workflow file in `.github/workflows/`

## Cost Comparison

| Solution | Cost | Setup Complexity |
|----------|------|------------------|
| Celery Beat + Redis (Render) | $7/month | High |
| External Cron Service | Free | Low |
| GitHub Actions | Free | Medium |

## Support

If you encounter issues:
1. Check Render logs for error messages
2. Verify all environment variables are set
3. Test webhook manually with curl
4. Check cron-job.org execution history
