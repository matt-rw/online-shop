#!/bin/bash
# Start Stripe webhook listener for local development
# Usage: ./scripts/stripe_listen.sh

STRIPE_CLI=~/stripe
ENV_FILE="$(dirname "$0")/../.env"
WEBHOOK_ENDPOINT="localhost:8000/shop/webhook/stripe/"

# Check if Stripe CLI exists
if [ ! -f "$STRIPE_CLI" ]; then
    echo "Stripe CLI not found at $STRIPE_CLI"
    exit 1
fi

# Kill any existing stripe listen processes
EXISTING_PIDS=$(pgrep -f "stripe.*listen" 2>/dev/null)
if [ -n "$EXISTING_PIDS" ]; then
    echo "Stopping existing Stripe listener(s)..."
    echo "$EXISTING_PIDS" | xargs kill 2>/dev/null
    sleep 1
fi

# Check if already logged in
if ! $STRIPE_CLI config --list &>/dev/null; then
    echo "Not logged in to Stripe. Logging in..."
    $STRIPE_CLI login
fi

echo ""
echo "Starting Stripe webhook listener..."
echo "Forwarding to: $WEBHOOK_ENDPOINT"
echo ""

# Start listener and capture the webhook secret
# The secret is printed on the first line of output
$STRIPE_CLI listen --forward-to "$WEBHOOK_ENDPOINT" 2>&1 | while IFS= read -r line; do
    echo "$line"

    # Look for the webhook signing secret in output
    if [[ "$line" =~ (whsec_[a-zA-Z0-9]+) ]]; then
        SECRET="${BASH_REMATCH[1]}"

        # Update .env file
        if [ -f "$ENV_FILE" ]; then
            if grep -q "^STRIPE_WEBHOOK_SECRET=" "$ENV_FILE"; then
                # Update existing key
                sed -i "s/^STRIPE_WEBHOOK_SECRET=.*/STRIPE_WEBHOOK_SECRET=$SECRET/" "$ENV_FILE"
                echo ""
                echo "✓ Updated STRIPE_WEBHOOK_SECRET in .env"
            else
                # Add new key
                echo "STRIPE_WEBHOOK_SECRET=$SECRET" >> "$ENV_FILE"
                echo ""
                echo "✓ Added STRIPE_WEBHOOK_SECRET to .env"
            fi
        else
            echo ""
            echo "Warning: .env file not found at $ENV_FILE"
            echo "Webhook secret: $SECRET"
        fi
    fi
done
