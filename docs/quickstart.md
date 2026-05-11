# Quick Start Guide

Get vision.poker up and running in 15 minutes.

## Prerequisites

- Python 3.10+
- Stripe account
- Domain name (for production)

## Step 1: Clone Repository

```bash
git clone https://github.com/noobhanz/Vision.Poker.git
cd Vision.Poker
```

## Step 2: Set Up Stripe

1. Create account at [stripe.com](https://stripe.com)
2. Go to **Products > Add Product**
   - Name: Vision Pro
3. Add two prices:
   - Monthly: $36
   - Yearly: $360
4. Go to **Developers > API Keys** and copy:
   - Secret key (`sk_test_...`)
5. Go to **Developers > Webhooks > Add endpoint**
   - URL: `http://localhost:8000/stripe/webhook` (for now)
   - Events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy signing secret (`whsec_...`)

## Step 3: Set Up Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `backend/.env`:

```env
DATABASE_URL=sqlite:///./vision_poker.db
STRIPE_SECRET_KEY=sk_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_secret
STRIPE_PRICE_ID_MONTHLY=price_your_monthly_id
STRIPE_PRICE_ID_YEARLY=price_your_yearly_id
SECRET_KEY=run-python-c-import-secrets-print-secrets-token-hex-32
TRIAL_DAYS=7
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

Test it:
```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

## Step 4: Test Stripe Webhooks Locally

In a new terminal:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks
stripe listen --forward-to localhost:8000/stripe/webhook
```

## Step 5: Set Up Desktop App

In a new terminal:

```bash
cd /path/to/Vision.Poker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
```

Edit `.env`:

```env
POKER_CLIENT_TITLE=PokerStars
MULTI_TABLE_MODE=true
HUD_HOTKEY=F9
```

## Step 6: Update API URLs

For local development, update the API URL:

**In `licensing/validator.py`:**
```python
API_URL = "http://localhost:8000"
```

**In `website/index.html`:**
```javascript
const API_URL = 'http://localhost:8000';
```

## Step 7: Test the Full Flow

### A. Test Signup

1. Open `website/index.html` in browser
2. Click "Start Free Trial"
3. Enter your email
4. You'll be redirected to Stripe Checkout
5. Use test card: `4242 4242 4242 4242`
6. After payment, you'll see your license key

### B. Test Desktop App

```bash
python app.py
```

1. License entry dialog appears
2. Enter the license key from step A
3. App starts and shows in menu bar
4. Open a poker client
5. Click "Start HUD"

## Step 8: Deploy for Production

### Deploy Backend

Choose a platform:

**Railway (easiest):**
1. Push to GitHub
2. Connect repo to Railway
3. Add environment variables
4. Deploy

**Or manually:**
```bash
# On your server
git clone https://github.com/noobhanz/Vision.Poker.git
cd Vision.Poker/backend
pip install -r requirements.txt
# Configure .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Update URLs

Once deployed, update:

1. **Stripe webhook URL** to production endpoint
2. **`licensing/validator.py`** `API_URL`
3. **`website/index.html`** `API_URL`

### Deploy Landing Page

Host `website/index.html` on:
- GitHub Pages
- Netlify
- Vercel
- Any static hosting

### Build Desktop App

```bash
pip install py2app
python setup_app.py py2app
# Creates dist/Vision Poker.app
```

## Checklist

- [ ] Stripe account created
- [ ] Products and prices configured
- [ ] Webhook endpoint added
- [ ] Backend deployed
- [ ] Landing page deployed
- [ ] Desktop app built
- [ ] API URLs updated to production
- [ ] Test full signup flow
- [ ] Test license validation
- [ ] Test payment failure handling

## Common Issues

### "Module not found"

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
```

### "Stripe webhook failed"

Check that:
- Webhook secret matches
- Endpoint URL is correct
- Server is running

### "License validation failed"

Check that:
- Backend is running
- API_URL is correct
- License key is valid

## Next Steps

1. Read [stripe.md](stripe.md) for payment details
2. Read [backend.md](backend.md) for deployment options
3. Read [distribution.md](distribution.md) for app building
4. Read [licensing.md](licensing.md) for license system details
