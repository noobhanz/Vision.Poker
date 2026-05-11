"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from .models import SubscriptionStatus


# User schemas
class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# License schemas
class LicenseResponse(BaseModel):
    """Schema for license response."""
    license_key: str
    is_active: bool
    created_at: datetime
    activated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LicenseValidateRequest(BaseModel):
    """Schema for validating a license."""
    license_key: str
    machine_id: Optional[str] = None


class LicenseValidateResponse(BaseModel):
    """Schema for license validation response."""
    valid: bool
    status: SubscriptionStatus
    days_remaining: int
    message: str
    requires_payment: bool = False
    checkout_url: Optional[str] = None


class LicenseActivateRequest(BaseModel):
    """Schema for activating a license on a machine."""
    license_key: str
    machine_id: str


# Subscription schemas
class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    status: SubscriptionStatus
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    days_remaining: int
    is_valid: bool

    class Config:
        from_attributes = True


# Checkout schemas
class CheckoutRequest(BaseModel):
    """Schema for creating a checkout session."""
    license_key: str
    price_type: str = "monthly"  # "monthly" or "yearly"


class CheckoutResponse(BaseModel):
    """Schema for checkout session response."""
    checkout_url: str
    session_id: str


# Signup flow
class SignupRequest(BaseModel):
    """Schema for new user signup."""
    email: EmailStr


class SignupResponse(BaseModel):
    """Schema for signup response."""
    user: UserResponse
    license_key: str
    trial_ends: datetime
    download_url: str
    message: str
