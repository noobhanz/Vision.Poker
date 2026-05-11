# Backend Deployment Guide

This guide covers deploying the vision.poker backend API.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Landing Page  │────▶│   Backend API   │────▶│     Stripe      │
│  (Static HTML)  │     │    (FastAPI)    │     │   (Payments)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │    Database     │
                        │    (SQLite/     │
                        │    PostgreSQL)  │
                        └─────────────────┘
```

## Local Development

### Prerequisites

- Python 3.10+
- pip or pipenv

### Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### Configure Environment

Edit `backend/.env`:

```env
# Database
DATABASE_URL=sqlite:///./vision_poker.db

# Stripe (from stripe.md setup)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_MONTHLY=price_...
STRIPE_PRICE_ID_YEARLY=price_...

# Application
SECRET_KEY=generate-a-random-string-here
TRIAL_DAYS=7
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at: http://localhost:8000
API docs at: http://localhost:8000/docs

## Production Deployment

### Option 1: Railway (Recommended for simplicity)

1. Create account at [railway.app](https://railway.app)
2. Connect your GitHub repository
3. Add environment variables in Railway dashboard
4. Deploy automatically on push

```bash
# Railway will auto-detect Python and run:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Option 2: Render

1. Create account at [render.com](https://render.com)
2. Create new Web Service
3. Connect GitHub repository
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables
6. Deploy

### Option 3: DigitalOcean App Platform

1. Create account at [digitalocean.com](https://digitalocean.com)
2. Go to App Platform > Create App
3. Connect GitHub repository
4. Configure as Python app
5. Add environment variables
6. Deploy

### Option 4: VPS (Manual Setup)

For a VPS (DigitalOcean Droplet, AWS EC2, etc.):

```bash
# SSH into server
ssh user@your-server-ip

# Install dependencies
sudo apt update
sudo apt install python3.11 python3.11-venv nginx certbot

# Clone repository
git clone https://github.com/noobhanz/Vision.Poker.git
cd Vision.Poker/backend

# Setup Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env  # Add your configuration

# Test the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Systemd Service

Create `/etc/systemd/system/visionpoker.service`:

```ini
[Unit]
Description=Vision Poker API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/user/Vision.Poker/backend
Environment="PATH=/home/user/Vision.Poker/backend/venv/bin"
EnvironmentFile=/home/user/Vision.Poker/backend/.env
ExecStart=/home/user/Vision.Poker/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visionpoker
sudo systemctl start visionpoker
sudo systemctl status visionpoker
```

#### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/api.vision.poker`:

```nginx
server {
    listen 80;
    server_name api.vision.poker;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and get SSL:

```bash
sudo ln -s /etc/nginx/sites-available/api.vision.poker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d api.vision.poker
```

## Database

### SQLite (Default)

Good for small scale. Data stored in `vision_poker.db`.

```env
DATABASE_URL=sqlite:///./vision_poker.db
```

### PostgreSQL (Production)

For production, use PostgreSQL:

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE visionpoker;
CREATE USER visionpoker WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE visionpoker TO visionpoker;
\q
```

Update `.env`:

```env
DATABASE_URL=postgresql://visionpoker:your-secure-password@localhost/visionpoker
```

Install driver:

```bash
pip install psycopg2-binary
```

### Database Migrations

For schema changes, use Alembic:

```bash
# Install alembic
pip install alembic

# Initialize (first time only)
alembic init migrations

# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## Monitoring & Logging

### Health Check

The API has a health endpoint:

```bash
curl https://api.vision.poker/health
# {"status": "healthy"}
```

### Logs

View logs:

```bash
# Systemd logs
sudo journalctl -u visionpoker -f

# Or if using Docker
docker logs -f visionpoker
```

### Error Tracking (Optional)

Add Sentry for error tracking:

```bash
pip install sentry-sdk[fastapi]
```

In `app/main.py`:

```python
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn")
```

## Security Checklist

- [ ] Use HTTPS (SSL certificate)
- [ ] Set strong `SECRET_KEY`
- [ ] Keep Stripe keys secure (never commit to git)
- [ ] Enable CORS only for your domains
- [ ] Use PostgreSQL for production
- [ ] Regular database backups
- [ ] Rate limiting (add `slowapi` package)
- [ ] Keep dependencies updated

## Useful Commands

```bash
# Check API status
curl https://api.vision.poker/

# Test signup
curl -X POST https://api.vision.poker/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Validate license
curl -X POST https://api.vision.poker/licenses/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key": "XXXX-XXXX-XXXX-XXXX"}'
```
