"""
vision.poker Backend API

FastAPI application providing:
- User signup and authentication
- License key generation and validation
- Stripe payment integration
- Download management
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db, init_db
from .routes import auth_router, licenses_router, stripe_router

# Initialize FastAPI
app = FastAPI(
    title="vision.poker API",
    description="Backend API for Vision Poker license management and payments",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(licenses_router)
app.include_router(stripe_router)


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "name": "vision.poker API",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    """Health check for load balancers."""
    return {"status": "healthy"}


@app.get("/download")
def download_redirect():
    """
    Redirect to latest download.

    In production, this would serve the actual installer
    or redirect to a signed S3/CloudFront URL.
    """
    # For now, redirect to GitHub releases or a placeholder
    return RedirectResponse(
        url="https://github.com/noobhanz/Vision.Poker/releases/latest",
        status_code=302,
    )


@app.get("/download/{platform}")
def download_platform(platform: str):
    """
    Platform-specific download.

    Args:
        platform: "mac", "windows", or "linux"
    """
    # Map platform to download URL
    downloads = {
        "mac": "https://github.com/noobhanz/Vision.Poker/releases/latest/download/VisionPoker.dmg",
        "windows": "https://github.com/noobhanz/Vision.Poker/releases/latest/download/VisionPoker.exe",
        "linux": "https://github.com/noobhanz/Vision.Poker/releases/latest/download/VisionPoker.AppImage",
    }

    url = downloads.get(platform.lower())
    if not url:
        return {"error": f"Unknown platform: {platform}"}

    return RedirectResponse(url=url, status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
