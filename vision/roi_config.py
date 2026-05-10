"""
Load skin-specific region-of-interest configs from config/skins/*.json.
ROI format: { "x": int, "y": int, "w": int, "h": int }
Supports relative coordinates (% of window size) for resolution independence.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ROIRegion:
    """A single region of interest."""

    x: int | float  # Absolute pixels or relative (0.0-1.0)
    y: int | float
    w: int | float
    h: int | float
    is_relative: bool = False

    def to_absolute(self, window_width: int, window_height: int) -> "ROIRegion":
        """Convert relative coordinates to absolute pixels."""
        if not self.is_relative:
            return self

        return ROIRegion(
            x=int(self.x * window_width),
            y=int(self.y * window_height),
            w=int(self.w * window_width),
            h=int(self.h * window_height),
            is_relative=False,
        )

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Return as (x, y, width, height) tuple."""
        return (int(self.x), int(self.y), int(self.w), int(self.h))

    def as_slice(self) -> tuple[slice, slice]:
        """Return as numpy array slices [y:y+h, x:x+w]."""
        return (
            slice(int(self.y), int(self.y) + int(self.h)),
            slice(int(self.x), int(self.x) + int(self.w)),
        )


@dataclass
class ROIConfig:
    """Configuration for all ROI regions in a poker skin."""

    # Hero cards
    hero_card_1: Optional[ROIRegion] = None
    hero_card_2: Optional[ROIRegion] = None

    # Board cards
    board_card_1: Optional[ROIRegion] = None
    board_card_2: Optional[ROIRegion] = None
    board_card_3: Optional[ROIRegion] = None
    board_card_4: Optional[ROIRegion] = None
    board_card_5: Optional[ROIRegion] = None

    # Text regions
    pot_size: Optional[ROIRegion] = None
    bet_to_call: Optional[ROIRegion] = None
    hero_stack: Optional[ROIRegion] = None

    # Villain stacks (up to 5)
    villain_stacks: list[ROIRegion] = field(default_factory=list)

    # Action area (to detect hero's turn)
    action_buttons: Optional[ROIRegion] = None

    # Metadata
    skin_name: str = ""
    base_resolution: tuple[int, int] = (1920, 1080)

    def get_hero_card_rois(self) -> list[ROIRegion]:
        """Get list of hero card ROIs."""
        rois = []
        if self.hero_card_1:
            rois.append(self.hero_card_1)
        if self.hero_card_2:
            rois.append(self.hero_card_2)
        return rois

    def get_board_card_rois(self) -> list[ROIRegion]:
        """Get list of board card ROIs."""
        rois = []
        for card in [
            self.board_card_1,
            self.board_card_2,
            self.board_card_3,
            self.board_card_4,
            self.board_card_5,
        ]:
            if card:
                rois.append(card)
        return rois

    def scale_to_window(self, window_width: int, window_height: int) -> "ROIConfig":
        """Scale all ROIs to match actual window dimensions."""
        base_w, base_h = self.base_resolution
        scale_x = window_width / base_w
        scale_y = window_height / base_h

        def scale_roi(roi: Optional[ROIRegion]) -> Optional[ROIRegion]:
            if roi is None:
                return None
            if roi.is_relative:
                return roi.to_absolute(window_width, window_height)
            return ROIRegion(
                x=int(roi.x * scale_x),
                y=int(roi.y * scale_y),
                w=int(roi.w * scale_x),
                h=int(roi.h * scale_y),
                is_relative=False,
            )

        return ROIConfig(
            hero_card_1=scale_roi(self.hero_card_1),
            hero_card_2=scale_roi(self.hero_card_2),
            board_card_1=scale_roi(self.board_card_1),
            board_card_2=scale_roi(self.board_card_2),
            board_card_3=scale_roi(self.board_card_3),
            board_card_4=scale_roi(self.board_card_4),
            board_card_5=scale_roi(self.board_card_5),
            pot_size=scale_roi(self.pot_size),
            bet_to_call=scale_roi(self.bet_to_call),
            hero_stack=scale_roi(self.hero_stack),
            villain_stacks=[scale_roi(vs) for vs in self.villain_stacks if vs],
            action_buttons=scale_roi(self.action_buttons),
            skin_name=self.skin_name,
            base_resolution=(window_width, window_height),
        )


def _parse_roi(data: dict) -> ROIRegion:
    """Parse a single ROI from JSON data."""
    is_relative = data.get("relative", False)

    # Support both "w"/"h" and "width"/"height" keys
    width = data.get("w", data.get("width", 0))
    height = data.get("h", data.get("height", 0))

    return ROIRegion(
        x=data.get("x", 0),
        y=data.get("y", 0),
        w=width,
        h=height,
        is_relative=is_relative,
    )


def load_skin_config(skin_name: str, config_dir: Optional[Path] = None) -> ROIConfig:
    """
    Load ROI configuration for a specific poker skin.

    Args:
        skin_name: Name of the skin (e.g., "pokerstars", "gg_poker")
        config_dir: Directory containing skin configs (default: config/skins/)

    Returns:
        ROIConfig populated from the JSON file
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / "config" / "skins"

    config_file = config_dir / f"{skin_name}.json"

    if not config_file.exists():
        raise FileNotFoundError(f"Skin config not found: {config_file}")

    with open(config_file) as f:
        data = json.load(f)

    config = ROIConfig(skin_name=skin_name)

    # Parse base resolution
    if "base_resolution" in data:
        res = data["base_resolution"]
        config.base_resolution = (res.get("width", 1920), res.get("height", 1080))

    # Parse hero cards
    if "hero_card_1" in data:
        config.hero_card_1 = _parse_roi(data["hero_card_1"])
    if "hero_card_2" in data:
        config.hero_card_2 = _parse_roi(data["hero_card_2"])

    # Parse board cards
    for i in range(1, 6):
        key = f"board_card_{i}"
        if key in data:
            setattr(config, key, _parse_roi(data[key]))

    # Parse text regions
    if "pot_size" in data:
        config.pot_size = _parse_roi(data["pot_size"])
    if "bet_to_call" in data:
        config.bet_to_call = _parse_roi(data["bet_to_call"])
    if "hero_stack" in data:
        config.hero_stack = _parse_roi(data["hero_stack"])

    # Parse villain stacks
    if "villain_stacks" in data:
        config.villain_stacks = [_parse_roi(vs) for vs in data["villain_stacks"]]

    # Parse action buttons
    if "action_buttons" in data:
        config.action_buttons = _parse_roi(data["action_buttons"])

    return config
