"""Database models for users, licenses, and subscriptions."""

import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base
from .config import settings


class SubscriptionStatus(str, Enum):
    """Subscription status states."""
    TRIAL = "trial"
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Stripe customer ID
    stripe_customer_id = Column(String, unique=True, nullable=True)

    # Relationships
    license = relationship("License", back_populates="user", uselist=False)
    subscription = relationship("Subscription", back_populates="user", uselist=False)


class License(Base):
    """Software license model."""

    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    license_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Hardware binding (optional - for single device enforcement)
    machine_id = Column(String, nullable=True)
    activated_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="license")

    @staticmethod
    def generate_key() -> str:
        """Generate a unique license key."""
        # Format: XXXX-XXXX-XXXX-XXXX (alphanumeric)
        segments = []
        for _ in range(4):
            segment = secrets.token_hex(2).upper()
            segments.append(segment)
        return "-".join(segments)


class Subscription(Base):
    """Stripe subscription tracking."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Stripe IDs
    stripe_subscription_id = Column(String, unique=True, nullable=True)
    stripe_price_id = Column(String, nullable=True)

    # Status
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)

    # Trial tracking
    trial_start = Column(DateTime, default=datetime.utcnow)
    trial_end = Column(DateTime, nullable=True)

    # Subscription dates
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="subscription")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set trial end date if not provided
        if self.trial_end is None and self.trial_start:
            self.trial_end = self.trial_start + timedelta(days=settings.trial_days)

    @property
    def is_valid(self) -> bool:
        """Check if subscription allows app usage."""
        now = datetime.utcnow()

        if self.status == SubscriptionStatus.TRIAL:
            return self.trial_end and now < self.trial_end

        if self.status == SubscriptionStatus.ACTIVE:
            return self.current_period_end and now < self.current_period_end

        return False

    @property
    def days_remaining(self) -> int:
        """Get days remaining in current period."""
        now = datetime.utcnow()

        if self.status == SubscriptionStatus.TRIAL and self.trial_end:
            delta = self.trial_end - now
            return max(0, delta.days)

        if self.status == SubscriptionStatus.ACTIVE and self.current_period_end:
            delta = self.current_period_end - now
            return max(0, delta.days)

        return 0
