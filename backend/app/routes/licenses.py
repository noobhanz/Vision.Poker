"""License validation and management routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import License, Subscription, SubscriptionStatus
from ..schemas import (
    LicenseActivateRequest,
    LicenseResponse,
    LicenseValidateRequest,
    LicenseValidateResponse,
)

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.post("/validate", response_model=LicenseValidateResponse)
def validate_license(request: LicenseValidateRequest, db: Session = Depends(get_db)):
    """
    Validate a license key.

    This is called by the desktop app on startup and periodically.
    Returns whether the app should run and any messages to display.
    """
    # Find license
    license = db.query(License).filter(License.license_key == request.license_key).first()

    if not license:
        return LicenseValidateResponse(
            valid=False,
            status=SubscriptionStatus.EXPIRED,
            days_remaining=0,
            message="Invalid license key.",
            requires_payment=False,
        )

    if not license.is_active:
        return LicenseValidateResponse(
            valid=False,
            status=SubscriptionStatus.EXPIRED,
            days_remaining=0,
            message="License has been revoked.",
            requires_payment=False,
        )

    # Check machine binding (if enabled)
    if license.machine_id and request.machine_id:
        if license.machine_id != request.machine_id:
            return LicenseValidateResponse(
                valid=False,
                status=SubscriptionStatus.EXPIRED,
                days_remaining=0,
                message="License is activated on a different device.",
                requires_payment=False,
            )

    # Get subscription status
    subscription = license.user.subscription
    if not subscription:
        return LicenseValidateResponse(
            valid=False,
            status=SubscriptionStatus.EXPIRED,
            days_remaining=0,
            message="No subscription found.",
            requires_payment=True,
            checkout_url=f"{settings.frontend_url}/checkout?license={license.license_key}",
        )

    # Check subscription validity
    if subscription.is_valid:
        days = subscription.days_remaining

        if subscription.status == SubscriptionStatus.TRIAL:
            if days <= 2:
                message = f"Trial ends in {days} day{'s' if days != 1 else ''}. Subscribe to continue."
            else:
                message = f"Trial active. {days} days remaining."
        else:
            message = "Subscription active."

        return LicenseValidateResponse(
            valid=True,
            status=subscription.status,
            days_remaining=days,
            message=message,
            requires_payment=subscription.status == SubscriptionStatus.TRIAL and days <= 2,
            checkout_url=f"{settings.frontend_url}/checkout?license={license.license_key}" if days <= 2 else None,
        )

    # Subscription expired
    return LicenseValidateResponse(
        valid=False,
        status=subscription.status,
        days_remaining=0,
        message="Your trial has expired. Subscribe to continue using Vision Poker.",
        requires_payment=True,
        checkout_url=f"{settings.frontend_url}/checkout?license={license.license_key}",
    )


@router.post("/activate", response_model=LicenseResponse)
def activate_license(request: LicenseActivateRequest, db: Session = Depends(get_db)):
    """
    Activate a license on a specific machine.

    This binds the license to a hardware ID for single-device enforcement.
    """
    license = db.query(License).filter(License.license_key == request.license_key).first()

    if not license:
        raise HTTPException(status_code=404, detail="License not found")

    if not license.is_active:
        raise HTTPException(status_code=400, detail="License has been revoked")

    # Check if already activated on different machine
    if license.machine_id and license.machine_id != request.machine_id:
        raise HTTPException(
            status_code=400,
            detail="License already activated on another device. Contact support to transfer."
        )

    # Activate on this machine
    if not license.machine_id:
        license.machine_id = request.machine_id
        license.activated_at = datetime.utcnow()
        db.commit()
        db.refresh(license)

    return license


@router.get("/{license_key}", response_model=LicenseResponse)
def get_license(license_key: str, db: Session = Depends(get_db)):
    """Get license details by key."""
    license = db.query(License).filter(License.license_key == license_key).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    return license
