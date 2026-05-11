# Environment Configuration Guide

This guide covers all environment variables for vision.poker.

## Desktop App Configuration

**File:** `.env` (project root)

```env
# Poker Client Settings
POKER_CLIENT_TITLE=PokerStars      # Window title to search for
SKIN_CONFIG=pokerstars             # Skin JSON file (pokerstars, gg_poker)

# Capture Settings
CAPTURE_FPS=2                      # Frames per second (1-10)
MULTI_TABLE_MODE=true              # Follow active poker window

# Vision Settings
YOLO_MODEL_PATH=models/cards.pt    # Path to YOLO model (optional)
CONFIDENCE_THRESHOLD=0.75          # Detection confidence (0.5-0.95)

# Engine Settings
MONTE_CARLO_N=5000                 # Equity simulations (1000-50000)

# HUD Settings
HUD_HOTKEY=F9                      # Toggle visibility key
HUD_OPACITY=0.88                   # Transparency (0.1-1.0)
HUD_POSITION=top-right             # top-left, top-right, bottom-left, bottom-right

# Debug
DEBUG_MODE=false                   # Save annotated frames to /debug/
```

### Settings Explained

| Setting | Default | Description |
|---------|---------|-------------|
| `POKER_CLIENT_TITLE` | PokerStars | Window title substring to find |
| `SKIN_CONFIG` | pokerstars | Which skin config to load for ROI |
| `CAPTURE_FPS` | 2 | How often to capture the screen |
| `MULTI_TABLE_MODE` | true | Follow active window for multi-table |
| `MONTE_CARLO_N` | 5000 | More = accurate but slower |
| `HUD_HOTKEY` | F9 | Press to show/hide HUD |
| `HUD_OPACITY` | 0.88 | 1.0 = fully opaque |
| `HUD_POSITION` | top-right | Corner for HUD placement |

## Backend API Configuration

**File:** `backend/.env`

```env
# Database
DATABASE_URL=sqlite:///./vision_poker.db

# For PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/visionpoker

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_MONTHLY=price_...
STRIPE_PRICE_ID_YEARLY=price_...

# Application
SECRET_KEY=your-random-secret-key
TRIAL_DAYS=7
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### Backend Settings Explained

| Setting | Required | Description |
|---------|----------|-------------|
| `DATABASE_URL` | Yes | Database connection string |
| `STRIPE_SECRET_KEY` | Yes | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Webhook signing secret |
| `STRIPE_PRICE_ID_MONTHLY` | Yes | Stripe price ID for $36/month |
| `STRIPE_PRICE_ID_YEARLY` | Yes | Stripe price ID for $360/year |
| `SECRET_KEY` | Yes | Random string for security |
| `TRIAL_DAYS` | No | Free trial length (default: 7) |
| `API_URL` | No | Backend URL for redirects |
| `FRONTEND_URL` | No | Landing page URL for redirects |

## License Validator Configuration

**File:** `licensing/validator.py`

Update the API URL for production:

```python
class LicenseValidator:
    API_URL = "https://api.vision.poker"  # Production
    # API_URL = "http://localhost:8000"   # Development
```

## Landing Page Configuration

**File:** `website/index.html`

Update the API URL in the script section:

```javascript
const API_URL = 'https://api.vision.poker';  // Production
// const API_URL = 'http://localhost:8000';  // Development
```

## Environment by Stage

### Development

```env
# Desktop .env
DEBUG_MODE=true
CAPTURE_FPS=1

# Backend .env
DATABASE_URL=sqlite:///./vision_poker_dev.db
STRIPE_SECRET_KEY=sk_test_...
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### Staging

```env
# Backend .env
DATABASE_URL=postgresql://user:pass@staging-db/visionpoker
STRIPE_SECRET_KEY=sk_test_...
API_URL=https://api-staging.vision.poker
FRONTEND_URL=https://staging.vision.poker
```

### Production

```env
# Backend .env
DATABASE_URL=postgresql://user:pass@prod-db/visionpoker
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_live_...
API_URL=https://api.vision.poker
FRONTEND_URL=https://vision.poker
SECRET_KEY=very-long-random-production-key
```

## Generating Secrets

### SECRET_KEY

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32
```

### Database Password

```bash
# Generate strong password
openssl rand -base64 24
```

## Environment Variable Precedence

1. Shell environment variables (highest)
2. `.env` file in working directory
3. Default values in code (lowest)

```bash
# Override via shell
CAPTURE_FPS=5 python app.py

# Or export
export CAPTURE_FPS=5
python app.py
```

## Security Notes

### Never Commit Secrets

Add to `.gitignore`:

```gitignore
.env
*.env
.env.*
!.env.example
```

### Use .env.example

Provide a template without real values:

```env
STRIPE_SECRET_KEY=sk_test_your_key_here
DATABASE_URL=sqlite:///./vision_poker.db
SECRET_KEY=generate-a-random-key
```

### Production Secrets

For production, use your platform's secret management:

- **Railway:** Environment variables in dashboard
- **Render:** Environment groups
- **AWS:** Secrets Manager or Parameter Store
- **Heroku:** Config vars

## Validation

### Check Desktop Config

```bash
python -c "from config.settings import Settings; s = Settings(); print(s)"
```

### Check Backend Config

```bash
cd backend
python -c "from app.config import settings; print(settings)"
```

### Test Stripe Connection

```bash
cd backend
python -c "
import stripe
from app.config import settings
stripe.api_key = settings.stripe_secret_key
print(stripe.Account.retrieve())
"
```
