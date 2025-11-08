# Email Subscriber Management Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Viewing Subscribers](#viewing-subscribers)
3. [Understanding Status Badges](#understanding-status-badges)
4. [Searching and Filtering](#searching-and-filtering)
5. [Exporting Subscriber Lists](#exporting-subscriber-lists)
6. [Common Tasks](#common-tasks)

---

## Getting Started

### Accessing the Admin Panel

1. Go to your website URL and add `/admin` at the end
   - Example: `https://yoursite.com/admin`

2. Log in with your admin credentials

3. Look for the **"Email Subscriptions"** section under the **"Shop"** app

4. Click on **"Email subscriptions"** to see all subscribers

---

## Viewing Subscribers

When you open the Email Subscriptions page, you'll see a list of all people who have signed up for your mailing list.

### What You'll See

Each subscriber entry shows:
- **Email address** - The subscriber's email
- **Status** - Whether they've confirmed their subscription (see below)
- **Subscribed at** - When they signed up
- **Source** - Where they signed up from (e.g., "homepage", "footer")

### Understanding the List Order

Subscribers are automatically sorted by **most recent first**, so new signups always appear at the top.

---

## Understanding Status Badges

Each subscriber has a colored status badge:

### ✓ Confirmed (Green Badge)
- The subscriber has confirmed their email address
- They will receive your marketing emails
- These are your active subscribers

### ⏳ Pending (Yellow Badge)
- The subscriber signed up but hasn't confirmed yet
- They won't receive emails until they confirm
- You may want to follow up with these subscribers

**Tip:** Focus your email campaigns on "Confirmed" subscribers to ensure deliverability.

---

## Searching and Filtering

### Searching by Email

1. Look for the **search box** at the top right of the subscriber list

2. Type any part of an email address
   - Example: Typing "gmail" will show all Gmail subscribers
   - Example: Typing "john" will show all emails containing "john"

3. Press **Enter** to search

4. Click the **"X"** button to clear the search

### Filtering Subscribers

On the right side of the page, you'll see filter options:

#### Filter by Confirmation Status
- Click **"Yes"** under "Is confirmed" to see only confirmed subscribers
- Click **"No"** to see only pending subscribers
- Click **"All"** to see everyone

#### Filter by Source
- Click any source (e.g., "homepage", "footer") to see where people signed up
- Useful for tracking which pages convert best

#### Filter by Date
- Use the date hierarchy at the top to browse by year, month, or day
- Click on a year to see all months
- Click on a month to see all days
- Click "Home" to return to all dates

### Combining Filters

You can use multiple filters at once:
- Example: Show only "Confirmed" subscribers from "homepage" who signed up in "January 2024"

---

## Exporting Subscriber Lists

Need to send your subscriber list to your email marketing service? Here's how to export:

### Step-by-Step Export

1. **Select subscribers** (optional):
   - Check the boxes next to specific subscribers, OR
   - Leave all unchecked to export everyone currently shown

2. **Choose the export action**:
   - Look for the dropdown menu above the subscriber list
   - Select **"Export selected to CSV"**

3. **Click "Go"** button

4. A file will download to your computer named `subscribers_YYYYMMDD.csv`
   - Example: `subscribers_20250107.csv`

### What's in the Export File

The CSV file contains four columns:
- **Email** - The subscriber's email address
- **Confirmed** - "Yes" or "No"
- **Subscribed Date** - When they signed up (format: YYYY-MM-DD HH:MM)
- **Source** - Where they signed up from

### Using the Export

You can open this file in:
- **Microsoft Excel** - For viewing and editing
- **Google Sheets** - Upload to Google Drive
- **Mailchimp, Constant Contact, etc.** - Import to your email service

**Pro Tip:** Export only confirmed subscribers for your email campaigns by:
1. Filter to show only "Confirmed" subscribers
2. Then export to CSV

---

## Common Tasks

### Task 1: Get All Active Subscribers for Email Campaign

**Goal:** Export a list of confirmed subscribers

1. Click the filter **"Is confirmed: Yes"** on the right side
2. Select **"Export selected to CSV"** from the action dropdown
3. Click **"Go"**
4. Use the downloaded CSV file in your email marketing tool

---

### Task 2: Check Recent Signups

**Goal:** See who signed up today or this week

1. Use the **date hierarchy** at the top
2. Click the current year
3. Click the current month
4. View today's signups or browse recent days

---

### Task 3: Find a Specific Subscriber

**Goal:** Check if someone is on your list

1. Use the **search box** at the top right
2. Type their email address (or part of it)
3. Press Enter

---

### Task 4: See Which Page Gets Most Signups

**Goal:** Track marketing effectiveness

1. Look at the **"Source"** filter on the right
2. Each source shows a count in parentheses
   - Example: "homepage (45)" means 45 signups from homepage
3. Click a source to see those subscribers

---

### Task 5: Follow Up with Pending Subscribers

**Goal:** Find subscribers who haven't confirmed

1. Filter by **"Is confirmed: No"**
2. Export this list to CSV
3. Consider sending a reminder email to confirm their subscription

**Note:** You may want to periodically clean up very old pending subscriptions (e.g., older than 30 days)

---

## Tips for Success

### Best Practices

1. **Export Regularly** - Back up your subscriber list monthly by exporting to CSV

2. **Monitor Confirmation Rates** - If many subscribers stay "Pending", your confirmation emails might not be reaching them

3. **Track Sources** - Use the source filter to see which pages convert best, then optimize those pages

4. **Clean Your List** - Periodically review pending subscribers and remove very old ones

### Data Privacy

Remember to:
- Only use email addresses for their intended purpose (marketing with consent)
- Honor unsubscribe requests promptly
- Keep subscriber data secure
- Comply with GDPR, CAN-SPAM, and other regulations

### Getting Help

If you need to:
- **Delete a subscriber** - Click their email, then click the red "Delete" button at the bottom
- **Edit subscriber details** - Click their email to view/edit
- **Bulk delete** - Select multiple subscribers, choose "Delete selected" action, click "Go"

---

## Troubleshooting

### "I don't see any subscribers"

- Check if filters are applied (right sidebar)
- Click "All" under each filter to reset
- Make sure your signup form is working on the website

### "Export button doesn't work"

- Make sure you selected "Export selected to CSV" from the dropdown
- Click the "Go" button after selecting the action
- Check your browser's download folder

### "Can't find a subscriber I know signed up"

- Try searching just part of their email
- Check if filters are limiting results
- Verify they actually completed the signup form

---

## Quick Reference

| Task | How To |
|------|--------|
| View all subscribers | Admin → Shop → Email subscriptions |
| See only confirmed | Filter: Is confirmed → Yes |
| See only pending | Filter: Is confirmed → No |
| Search by email | Use search box (top right) |
| Export to CSV | Action dropdown → Export selected to CSV → Go |
| View recent signups | Use date hierarchy at top |
| Check signup sources | View Source filter (right sidebar) |
| Find specific person | Search box → Type email → Enter |

---

**Questions?** Contact your website administrator or developer for technical support.
