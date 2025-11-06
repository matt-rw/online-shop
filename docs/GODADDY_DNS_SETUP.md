# GoDaddy DNS Setup for Render (Quick Guide)

## Step 1: Access GoDaddy DNS Settings

1. Log into **GoDaddy.com**
2. Click **"My Products"**
3. Find your domain (blueprintapparel.store)
4. Click **"DNS"** or **"Manage DNS"**

---

## Step 2: Remove Old Shopify DNS Records

**Find and DELETE these Shopify records:**

### Look for these patterns:
- **CNAME** records pointing to:
  - `shops.myshopify.com`
  - `shop.shopify.com`
  - Any `.myshopify.com` domain

- **A** records pointing to Shopify IPs:
  - `23.227.38.65`
  - `23.227.38.32`
  - Or other Shopify IPs

### How to delete:
1. Click the **pencil icon** or **Edit** next to the record
2. Click **Delete** or **Remove**
3. Confirm deletion

> **Tip**: Take a screenshot of existing records before deleting, just in case!

---

## Step 3: Add Render DNS Records

### Add TWO new records:

### Record 1: Root Domain (A Record)
| Setting | Value |
|---------|-------|
| **Type** | A |
| **Name** | @ |
| **Value** | `216.24.57.1` |
| **TTL** | 600 (or 1 hour) |

**Steps:**
1. Click **"Add"** or **"Add Record"**
2. Select **"A"** as type
3. Name: `@` (means root domain)
4. Value: `216.24.57.1`
5. TTL: `600` seconds
6. Click **Save**

---

### Record 2: WWW Subdomain (CNAME Record)
| Setting | Value |
|---------|-------|
| **Type** | CNAME |
| **Name** | www |
| **Value** | `your-app-name.onrender.com` |
| **TTL** | 600 (or 1 hour) |

**Steps:**
1. Click **"Add"** or **"Add Record"**
2. Select **"CNAME"** as type
3. Name: `www`
4. Value: `your-app-name.onrender.com` (get this from Render dashboard)
5. TTL: `600` seconds
6. Click **Save**

> **Important**: Replace `your-app-name.onrender.com` with your actual Render URL!

---

## Step 4: What Your DNS Should Look Like

After setup, your DNS records should include:

```
Type    Name    Value                           TTL
─────────────────────────────────────────────────────
A       @       216.24.57.1                     600
CNAME   www     your-app-name.onrender.com      600
```

You may also see other records like:
- **NS** (nameserver) records - **DON'T DELETE THESE**
- **SOA** record - **DON'T DELETE THIS**
- Other records you need - keep them

---

## Step 5: Wait for DNS Propagation

- **Typical time**: 15 minutes to 2 hours
- **Maximum time**: 24-48 hours
- **Check progress**: Use https://dnschecker.org

### Test DNS resolution:
```bash
# Check if A record is working
dig blueprintapparel.store

# Check if CNAME is working
dig www.blueprintapparel.store

# Or use nslookup
nslookup blueprintapparel.store
nslookup www.blueprintapparel.store
```

---

## Common Issues & Solutions

### ❌ Issue: "This domain is already in use"
**Solution**: The domain is still linked to Shopify
1. Go to Shopify admin
2. Remove domain from Shopify settings
3. Wait 1 hour
4. Try again in GoDaddy

### ❌ Issue: Can't delete old DNS records
**Solution**: Make sure you're not trying to delete NS or SOA records
- Only delete A and CNAME records pointing to Shopify
- Keep NS and SOA records

### ❌ Issue: Changes not taking effect
**Solution**:
1. Clear your browser cache
2. Wait longer (DNS can take time)
3. Try in incognito/private window
4. Check DNS with `dig` command

### ❌ Issue: "DNS_PROBE_FINISHED_NXDOMAIN" error
**Solution**:
1. DNS hasn't propagated yet - wait longer
2. Verify DNS records are correct
3. Check for typos in domain name

---

## Video Tutorial (if you need visual help)

GoDaddy has official tutorials:
- Search YouTube: "GoDaddy change DNS records"
- Or visit: https://www.godaddy.com/help/manage-dns-records-680

---

## After DNS is Working

1. Add custom domain in Render (see main DEPLOYMENT.md)
2. Wait for SSL certificate (automatic, takes 5-10 minutes)
3. Visit https://blueprintapparel.store
4. Celebrate! 🎉

---

## Need Help?

If you're stuck on GoDaddy DNS:
1. Check the main **DEPLOYMENT.md** file
2. Contact GoDaddy support (they're usually helpful with DNS)
3. Use DNS checker tools: https://dnschecker.org
