# Licensing System Guide

This guide explains the vision.poker licensing system architecture.

## Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Website   │────▶│   Backend   │────▶│   Stripe    │
│   Signup    │     │   License   │     │   Payment   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Desktop    │
                    │    App      │
                    └─────────────┘
```

## License Flow

### 1. User Signs Up

```
User enters email → Backend creates:
├── User account
├── License key (XXXX-XXXX-XXXX-XXXX)
└── Trial subscription (7 days)
```

### 2. User Pays (or starts trial)

```
Stripe Checkout → On success:
├── Webhook received
└── Subscription status: ACTIVE
```

### 3. User Downloads App

```
User downloads → Enters license key:
├── App calls /licenses/activate
├── Machine ID bound to license
└── App runs
```

### 4. Periodic Validation

```
Every hour (and on startup):
├── App calls /licenses/validate
├── If valid: continue
├── If trial expiring: show reminder
└── If expired: lock app, show payment
```

## License Key Format

```
XXXX-XXXX-XXXX-XXXX
│    │    │    │
└────┴────┴────┴── 16 alphanumeric characters (uppercase)
```

Generated using cryptographically secure random:

```python
import secrets
key = "-".join(secrets.token_hex(2).upper() for _ in range(4))
# Example: "A3B2-C9D1-E5F4-G7H8"
```

## Subscription States

| Status | Can Run | Description |
|--------|---------|-------------|
| `TRIAL` | Yes | Within 7-day trial period |
| `ACTIVE` | Yes | Paid subscription active |
| `TRIAL_EXPIRING` | Yes | Trial ends in ≤2 days (show warning) |
| `PAST_DUE` | No | Payment failed, awaiting retry |
| `CANCELED` | No* | User canceled (runs until period end) |
| `EXPIRED` | No | Trial or subscription ended |

## Machine Binding

Licenses are bound to a single machine to prevent sharing.

### Machine ID Generation

```python
# macOS: Hardware UUID
ioreg -rd1 -c IOPlatformExpertDevice | grep IOPlatformUUID

# Windows: Machine GUID
reg query HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography /v MachineGuid

# Linux: /etc/machine-id
cat /etc/machine-id
```

Hashed for privacy:

```python
machine_id = hashlib.sha256(hardware_id.encode()).hexdigest()[:32]
```

### Transfer Process

If user gets new computer:

1. User contacts support
2. Admin clears `machine_id` in database
3. User re-activates on new machine

## API Endpoints

### POST /auth/signup

Create new user with trial license.

**Request:**
```json
{
    "email": "user@example.com"
}
```

**Response:**
```json
{
    "user": {"id": 1, "email": "user@example.com"},
    "license_key": "A3B2-C9D1-E5F4-G7H8",
    "trial_ends": "2024-01-08T00:00:00Z",
    "download_url": "/download",
    "message": "Welcome! Your 7-day trial has started."
}
```

### POST /licenses/validate

Check if license allows app to run.

**Request:**
```json
{
    "license_key": "A3B2-C9D1-E5F4-G7H8",
    "machine_id": "abc123..."
}
```

**Response (Valid):**
```json
{
    "valid": true,
    "status": "trial",
    "days_remaining": 5,
    "message": "Trial active. 5 days remaining.",
    "requires_payment": false
}
```

**Response (Expired):**
```json
{
    "valid": false,
    "status": "expired",
    "days_remaining": 0,
    "message": "Your trial has expired. Subscribe to continue.",
    "requires_payment": true,
    "checkout_url": "https://vision.poker/checkout?license=..."
}
```

### POST /licenses/activate

Bind license to a machine.

**Request:**
```json
{
    "license_key": "A3B2-C9D1-E5F4-G7H8",
    "machine_id": "abc123..."
}
```

**Response:**
```json
{
    "license_key": "A3B2-C9D1-E5F4-G7H8",
    "is_active": true,
    "activated_at": "2024-01-01T12:00:00Z"
}
```

## Desktop App Integration

### Startup Flow

```python
def check_license_startup():
    validator = LicenseValidator()

    # No license stored?
    if not validator.has_license:
        # Show license entry dialog
        dialog = LicenseEntryDialog(validator)
        if dialog.exec() != Accepted:
            sys.exit(1)

    # Validate license
    result = validator.validate()

    if not result.can_run:
        # Show payment required dialog
        dialog = TrialExpiredDialog(validator, result)
        dialog.exec()
        sys.exit(1)

    # License valid, continue to app
    return validator
```

### Periodic Check

```python
class App:
    def __init__(self):
        # Check every hour
        self.license_timer = Timer(self.check_license, 3600)
        self.license_timer.start()

    def check_license(self):
        result = self.validator.validate()

        if not result.can_run:
            self.stop_hud()
            self.show_payment_dialog()
```

### Local Storage

License key stored in user's app data:

```
macOS:   ~/Library/Application Support/VisionPoker/license.json
Windows: %LOCALAPPDATA%\VisionPoker\license.json
Linux:   ~/.config/visionpoker/license.json
```

Content:
```json
{
    "license_key": "A3B2-C9D1-E5F4-G7H8",
    "machine_id": "abc123..."
}
```

## Offline Handling

If network is unavailable:

1. **First launch:** Fails (cannot validate new license)
2. **Subsequent launches:** Allow grace period
3. **Extended offline:** Eventually lock until online

```python
if result.status == LicenseStatus.NETWORK_ERROR:
    # Allow brief offline usage
    result.can_run = True
```

For stricter enforcement, implement offline token with expiry.

## Admin Operations

### Revoke License

```sql
UPDATE licenses SET is_active = false, revoked_at = NOW()
WHERE license_key = 'XXXX-XXXX-XXXX-XXXX';
```

### Transfer License

```sql
UPDATE licenses SET machine_id = NULL, activated_at = NULL
WHERE license_key = 'XXXX-XXXX-XXXX-XXXX';
```

### Extend Trial

```sql
UPDATE subscriptions SET trial_end = trial_end + INTERVAL '7 days'
WHERE user_id = (SELECT user_id FROM licenses WHERE license_key = 'XXXX-XXXX-XXXX-XXXX');
```

### Grant Free Access

```sql
UPDATE subscriptions
SET status = 'active',
    current_period_end = '2099-12-31'
WHERE user_id = 123;
```

## Security Considerations

### License Key Security

- Keys are randomly generated (cryptographically secure)
- Keys are hashed when stored/transmitted where appropriate
- Rate limiting on validation endpoint

### Machine ID Privacy

- Hardware IDs are hashed before sending
- Only hash is stored, not raw hardware info
- Cannot reverse engineer original hardware ID

### API Security

- HTTPS only
- Rate limiting to prevent brute force
- Webhook signatures verified

### Preventing Piracy

1. **Machine binding:** One device per license
2. **Server validation:** Can't fake local validation
3. **Periodic checks:** Can't use expired license indefinitely
4. **Obfuscation:** Consider PyArmor for code protection

## Troubleshooting

### "Invalid license key"

- Check for typos (letters/numbers confusion: 0/O, 1/I)
- Verify key exists in database
- Check if key was revoked

### "License activated on another device"

- User needs to transfer license (admin clears machine_id)
- Or they need another license

### "Network error during validation"

- Check internet connection
- Verify API_URL is correct
- Check if API is running

### Trial not extending after payment

- Check Stripe webhook logs
- Verify webhook endpoint is receiving events
- Check subscription status in database
