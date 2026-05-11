"""Backend configuration."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """API configuration loaded from environment."""

    # Database
    database_url: str = "sqlite:///./vision_poker.db"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_monthly: str = ""  # Price ID for $36/month
    stripe_price_id_yearly: str = ""   # Price ID for $360/year

    # App
    secret_key: str = "change-me-in-production"
    trial_days: int = 7
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
