"""Stripe payment routes and webhooks."""

from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import License, Subscription, SubscriptionStatus, User
from ..schemas import CheckoutRequest, CheckoutResponse

router = APIRouter(prefix="/stripe", tags=["stripe"])

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout_session(request: CheckoutRequest, db: Session = Depends(get_db)):
    """
    Create a Stripe Checkout session for subscription.

    Called when user clicks "Subscribe" after trial or from payment prompt.
    """
    # Find license and user
    license = db.query(License).filter(License.license_key == request.license_key).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")

    user = license.user

    # Get or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"license_key": license.license_key},
        )
        user.stripe_customer_id = customer.id
        db.commit()

    # Select price based on billing period
    if request.price_type == "yearly":
        price_id = settings.stripe_price_id_yearly
    else:
        price_id = settings.stripe_price_id_monthly

    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price not configured")

    # Create checkout session
    try:
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{settings.frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/cancel",
            metadata={
                "license_key": license.license_key,
                "user_id": str(user.id),
            },
            subscription_data={
                "metadata": {
                    "license_key": license.license_key,
                    "user_id": str(user.id),
                },
            },
        )

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed: New subscription started
    - invoice.paid: Recurring payment successful
    - invoice.payment_failed: Payment failed
    - customer.subscription.updated: Subscription status changed
    - customer.subscription.deleted: Subscription canceled
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data, db)

    elif event_type == "invoice.paid":
        await handle_invoice_paid(data, db)

    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data, db)

    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data, db)

    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data, db)

    return {"status": "success"}


async def handle_checkout_completed(session: dict, db: Session):
    """Handle successful checkout - activate subscription."""
    license_key = session.get("metadata", {}).get("license_key")
    subscription_id = session.get("subscription")

    if not license_key or not subscription_id:
        return

    license = db.query(License).filter(License.license_key == license_key).first()
    if not license:
        return

    subscription = license.user.subscription
    if not subscription:
        return

    # Get subscription details from Stripe
    stripe_sub = stripe.Subscription.retrieve(subscription_id)

    # Update subscription status
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.stripe_subscription_id = subscription_id
    subscription.stripe_price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    subscription.current_period_start = datetime.fromtimestamp(stripe_sub["current_period_start"])
    subscription.current_period_end = datetime.fromtimestamp(stripe_sub["current_period_end"])

    db.commit()


async def handle_invoice_paid(invoice: dict, db: Session):
    """Handle successful recurring payment."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()

    if not subscription:
        return

    # Get updated period from Stripe
    stripe_sub = stripe.Subscription.retrieve(subscription_id)

    subscription.status = SubscriptionStatus.ACTIVE
    subscription.current_period_start = datetime.fromtimestamp(stripe_sub["current_period_start"])
    subscription.current_period_end = datetime.fromtimestamp(stripe_sub["current_period_end"])

    db.commit()


async def handle_payment_failed(invoice: dict, db: Session):
    """Handle failed payment - lock the app."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()

    if not subscription:
        return

    # Mark as past due - app will prompt for payment update
    subscription.status = SubscriptionStatus.PAST_DUE

    db.commit()


async def handle_subscription_updated(stripe_sub: dict, db: Session):
    """Handle subscription status changes."""
    subscription_id = stripe_sub.get("id")

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()

    if not subscription:
        return

    # Map Stripe status to our status
    stripe_status = stripe_sub.get("status")
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.EXPIRED,
    }

    new_status = status_map.get(stripe_status, SubscriptionStatus.EXPIRED)
    subscription.status = new_status

    # Update period dates
    subscription.current_period_start = datetime.fromtimestamp(stripe_sub["current_period_start"])
    subscription.current_period_end = datetime.fromtimestamp(stripe_sub["current_period_end"])

    if stripe_sub.get("canceled_at"):
        subscription.canceled_at = datetime.fromtimestamp(stripe_sub["canceled_at"])

    db.commit()


async def handle_subscription_deleted(stripe_sub: dict, db: Session):
    """Handle subscription cancellation."""
    subscription_id = stripe_sub.get("id")

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()

    if not subscription:
        return

    subscription.status = SubscriptionStatus.CANCELED
    subscription.canceled_at = datetime.utcnow()

    db.commit()


@router.post("/create-portal-session")
def create_portal_session(license_key: str, db: Session = Depends(get_db)):
    """
    Create a Stripe Customer Portal session.

    Allows users to manage their subscription (update payment, cancel, etc.)
    """
    license = db.query(License).filter(License.license_key == license_key).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")

    user = license.user
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")

    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{settings.frontend_url}/account",
        )
        return {"url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
