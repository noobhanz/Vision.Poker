"""Authentication and signup routes."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import License, Subscription, SubscriptionStatus, User
from ..schemas import SignupRequest, SignupResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account with trial license.

    Returns license key and download URL.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        # Return existing license if user already signed up
        if existing_user.license:
            return SignupResponse(
                user=UserResponse.model_validate(existing_user),
                license_key=existing_user.license.license_key,
                trial_ends=existing_user.subscription.trial_end if existing_user.subscription else datetime.utcnow(),
                download_url=f"{settings.api_url}/download",
                message="Account already exists. Here's your license key.",
            )
        raise HTTPException(status_code=400, detail="Account exists but has no license. Contact support.")

    # Create user
    user = User(email=request.email)
    db.add(user)
    db.flush()  # Get user ID

    # Create license
    license = License(
        user_id=user.id,
        license_key=License.generate_key(),
    )
    db.add(license)

    # Create trial subscription
    trial_start = datetime.utcnow()
    trial_end = trial_start + timedelta(days=settings.trial_days)

    subscription = Subscription(
        user_id=user.id,
        status=SubscriptionStatus.TRIAL,
        trial_start=trial_start,
        trial_end=trial_end,
    )
    db.add(subscription)

    db.commit()
    db.refresh(user)
    db.refresh(license)
    db.refresh(subscription)

    return SignupResponse(
        user=UserResponse.model_validate(user),
        license_key=license.license_key,
        trial_ends=trial_end,
        download_url=f"{settings.api_url}/download",
        message=f"Welcome! Your {settings.trial_days}-day trial has started.",
    )


@router.get("/user/{email}", response_model=UserResponse)
def get_user(email: str, db: Session = Depends(get_db)):
    """Get user by email."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
