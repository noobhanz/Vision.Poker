"""License validation against the backend API."""

import webbrowser
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

from .storage import LicenseStorage, get_machine_id


class LicenseStatus(Enum):
    """License validation status."""
    VALID = "valid"
    TRIAL = "trial"
    TRIAL_EXPIRING = "trial_expiring"
    EXPIRED = "expired"
    INVALID = "invalid"
    PAYMENT_REQUIRED = "payment_required"
    NETWORK_ERROR = "network_error"
    NO_LICENSE = "no_license"


@dataclass
class ValidationResult:
    """Result of license validation."""
    status: LicenseStatus
    days_remaining: int
    message: str
    checkout_url: Optional[str] = None
    can_run: bool = False


class LicenseValidator:
    """
    Validate licenses against the backend API.

    Usage:
        validator = LicenseValidator()

        # Check on startup
        result = validator.validate()
        if not result.can_run:
            validator.prompt_for_payment(result)
            sys.exit(1)

        # Periodic check (every hour)
        result = validator.validate()
        if not result.can_run:
            # Show payment dialog
    """

    API_URL = "https://api.vision.poker"  # Production URL
    # API_URL = "http://localhost:8000"  # Development

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or self.API_URL
        self.storage = LicenseStorage()
        self._cached_result: Optional[ValidationResult] = None

    def validate(self, force: bool = False) -> ValidationResult:
        """
        Validate the stored license key.

        Args:
            force: Skip cache and always call API

        Returns:
            ValidationResult with status and can_run flag
        """
        license_key = self.storage.load_license()

        if not license_key:
            return ValidationResult(
                status=LicenseStatus.NO_LICENSE,
                days_remaining=0,
                message="No license found. Please enter your license key.",
                can_run=False,
            )

        try:
            response = httpx.post(
                f"{self.api_url}/licenses/validate",
                json={
                    "license_key": license_key,
                    "machine_id": get_machine_id(),
                },
                timeout=10.0,
            )

            if response.status_code != 200:
                return ValidationResult(
                    status=LicenseStatus.INVALID,
                    days_remaining=0,
                    message="License validation failed.",
                    can_run=False,
                )

            data = response.json()

            # Determine status
            if data["valid"]:
                if data["status"] == "trial":
                    if data["days_remaining"] <= 2:
                        status = LicenseStatus.TRIAL_EXPIRING
                    else:
                        status = LicenseStatus.TRIAL
                else:
                    status = LicenseStatus.VALID

                return ValidationResult(
                    status=status,
                    days_remaining=data["days_remaining"],
                    message=data["message"],
                    checkout_url=data.get("checkout_url"),
                    can_run=True,
                )
            else:
                # Not valid - check if payment required
                if data.get("requires_payment"):
                    status = LicenseStatus.PAYMENT_REQUIRED
                else:
                    status = LicenseStatus.EXPIRED

                return ValidationResult(
                    status=status,
                    days_remaining=0,
                    message=data["message"],
                    checkout_url=data.get("checkout_url"),
                    can_run=False,
                )

        except httpx.RequestError:
            # Network error - allow offline grace period
            return ValidationResult(
                status=LicenseStatus.NETWORK_ERROR,
                days_remaining=0,
                message="Unable to validate license. Check your internet connection.",
                can_run=True,  # Allow brief offline usage
            )

    def activate(self, license_key: str) -> ValidationResult:
        """
        Activate a new license key.

        Args:
            license_key: The license key to activate

        Returns:
            ValidationResult
        """
        try:
            response = httpx.post(
                f"{self.api_url}/licenses/activate",
                json={
                    "license_key": license_key,
                    "machine_id": get_machine_id(),
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                # Save license locally
                self.storage.save_license(license_key)
                # Validate to get full status
                return self.validate()

            elif response.status_code == 400:
                data = response.json()
                return ValidationResult(
                    status=LicenseStatus.INVALID,
                    days_remaining=0,
                    message=data.get("detail", "Activation failed."),
                    can_run=False,
                )
            else:
                return ValidationResult(
                    status=LicenseStatus.INVALID,
                    days_remaining=0,
                    message="License activation failed.",
                    can_run=False,
                )

        except httpx.RequestError:
            return ValidationResult(
                status=LicenseStatus.NETWORK_ERROR,
                days_remaining=0,
                message="Network error during activation.",
                can_run=False,
            )

    def open_checkout(self, result: ValidationResult) -> bool:
        """
        Open the checkout URL in the default browser.

        Args:
            result: ValidationResult containing checkout_url

        Returns:
            True if URL was opened
        """
        if result.checkout_url:
            webbrowser.open(result.checkout_url)
            return True
        return False

    def get_checkout_url(self, price_type: str = "monthly") -> Optional[str]:
        """
        Get a checkout URL for the current license.

        Args:
            price_type: "monthly" or "yearly"

        Returns:
            Checkout URL or None
        """
        license_key = self.storage.load_license()
        if not license_key:
            return None

        try:
            response = httpx.post(
                f"{self.api_url}/stripe/create-checkout",
                json={
                    "license_key": license_key,
                    "price_type": price_type,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json().get("checkout_url")

        except httpx.RequestError:
            pass

        return None

    @property
    def has_license(self) -> bool:
        """Check if a license key is stored locally."""
        return self.storage.load_license() is not None

    @property
    def license_key(self) -> Optional[str]:
        """Get the stored license key."""
        return self.storage.load_license()
