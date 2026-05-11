# Stripe Setup Guide

This guide walks through setting up Stripe for vision.poker subscriptions.

## 1. Create Stripe Account

1. Go to [stripe.com](https://stripe.com) and create an account
2. Complete business verification (required for live payments)
3. Access the [Stripe Dashboard](https://dashboard.stripe.com)

## 2. Get API Keys

1. Go to **Developers > API Keys**
2. Copy your keys:
   - **Publishable key:** `pk_test_...` (for frontend, not currently used)
   - **Secret key:** `sk_test_...` (for backend)

For production:
- Toggle "Test mode" off to get live keys
- Live keys start with `pk_live_` and `sk_live_`

## 3. Create Products and Prices

### Create the Product

1. Go to **Products > Add Product**
2. Fill in:
   - **Name:** Vision Pro
   - **Description:** Real-time poker HUD overlay
3. Click **Save product**

### Create Pricing

Add two prices to the product:

**Monthly Price:**
1. Click **Add price**
2. Configure:
   - **Price:** $36.00
   - **Billing period:** Monthly
   - **Price ID:** Copy this (e.g., `price_1ABC123...`)

**Yearly Price:**
1. Click **Add another price**
2. Configure:
   - **Price:** $360.00
   - **Billing period:** Yearly
   - **Price ID:** Copy this (e.g., `price_1DEF456...`)

## 4. Set Up Webhooks

Webhooks notify your backend when payment events occur.

### Create Webhook Endpoint

1. Go to **Developers > Webhooks**
2. Click **Add endpoint**
3. Configure:
   - **Endpoint URL:** `https://api.vision.poker/stripe/webhook`
   - **Events to listen for:**
     - `checkout.session.completed`
     - `invoice.paid`
     - `invoice.payment_failed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
4. Click **Add endpoint**
5. Copy the **Signing secret** (`whsec_...`)

### Test Webhooks Locally

For local development, use Stripe CLI:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/stripe/webhook

# Copy the webhook signing secret it displays
```

## 5. Configure Environment Variables

Add these to your `backend/.env`:

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRICE_ID_MONTHLY=price_monthly_price_id
STRIPE_PRICE_ID_YEARLY=price_yearly_price_id
```

## 6. Customer Portal Setup

Allow customers to manage their subscriptions:

1. Go to **Settings > Billing > Customer portal**
2. Configure allowed actions:
   - Update payment methods: **On**
   - Cancel subscriptions: **On**
   - Switch plans: **On** (optional)
3. Save changes

The portal URL is automatically created when users click "Manage Subscription."

## 7. Test the Integration

### Test Cards

Use these test card numbers:

| Scenario | Card Number |
|----------|-------------|
| Successful payment | 4242 4242 4242 4242 |
| Declined | 4000 0000 0000 0002 |
| Requires authentication | 4000 0025 0000 3155 |
| Insufficient funds | 4000 0000 0000 9995 |

Use any future expiry date and any 3-digit CVC.

### Test the Flow

1. Start your backend server
2. Go to your landing page
3. Click "Start Free Trial"
4. Enter email, continue to checkout
5. Use test card `4242 4242 4242 4242`
6. Verify webhook received in Stripe Dashboard > Webhooks > Recent events

## 8. Go Live Checklist

Before accepting real payments:

- [ ] Complete Stripe business verification
- [ ] Switch to live API keys
- [ ] Update webhook endpoint to production URL
- [ ] Create new webhook with live signing secret
- [ ] Test with a real card (refund immediately)
- [ ] Set up Stripe Radar for fraud protection
- [ ] Configure receipt emails in Stripe Dashboard

## Troubleshooting

### Webhook Signature Verification Failed

- Ensure `STRIPE_WEBHOOK_SECRET` matches the endpoint's signing secret
- For local testing, use the secret from `stripe listen` output
- Production webhook secrets are different from test secrets

### Price Not Found

- Verify price IDs in environment variables
- Ensure prices are active (not archived)
- Check you're using the correct mode (test vs live)

### Customer Portal Not Working

- Ensure portal is configured in Stripe Dashboard
- Customer must have a Stripe customer ID (created on first checkout)

## Useful Links

- [Stripe Dashboard](https://dashboard.stripe.com)
- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe CLI](https://stripe.com/docs/stripe-cli)
- [Testing Webhooks](https://stripe.com/docs/webhooks/test)
- [Test Card Numbers](https://stripe.com/docs/testing#cards)
