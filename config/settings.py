"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from .env file."""

    poker_client_title: str = "PokerStars"  # window title substring
    skin_config: str = "pokerstars"  # which skin JSON to load
    capture_fps: int = 2
    monte_carlo_n: int = 5000
    yolo_model_path: str = "models/cards.pt"  # path to fine-tuned YOLOv8
    confidence_threshold: float = 0.75
    stable_frames_required: int = 2  # repeated active parses before HUD update
    hud_hotkey: str = "F9"
    hud_opacity: float = 0.88
    hud_position: str = "top-right"  # top-left | top-right | bottom-right
    multi_table_mode: bool = True  # follow active poker window (multi-table support)
    debug_mode: bool = False  # saves annotated frames to /debug/

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
