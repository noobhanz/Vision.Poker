"""Locate the poker table content inside a selected window frame."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from capture.window_finder import WindowRect


@dataclass(frozen=True)
class TableContentRect:
    """Detected parser content rectangle inside a captured frame."""

    x: int
    y: int
    width: int
    height: int
    confidence: float

    def as_window_rect(self, source: WindowRect) -> WindowRect:
        """Return a matching absolute WindowRect for the cropped frame."""
        return WindowRect(
            x=source.x + self.x,
            y=source.y + self.y,
            width=self.width,
            height=self.height,
            window_id=source.window_id,
            title=source.title,
        )


class PokerStarsTableLocator:
    """Find PokerStars table content from the green felt geometry."""

    # Empirical table-felt anchor in the existing PokerStars base skin.
    # This is not a card ROI. It is used only to infer the visible client
    # content rectangle when a selected window includes player chrome/borders.
    base_width = 955
    base_height = 688
    base_felt_x = 134
    base_felt_y = 156
    base_felt_w = 678
    base_felt_h = 315

    def locate(self, frame: np.ndarray) -> Optional[TableContentRect]:
        """Return the likely PokerStars content rect inside a captured frame."""
        import cv2

        if frame.size == 0:
            return None

        height, width = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
            hsv,
            np.array([35, 35, 20], dtype=np.uint8),
            np.array([95, 255, 230], dtype=np.uint8),
        )
        kernel = np.ones((17, 17), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        frame_area = float(width * height)
        if frame_area <= 0 or area / frame_area < 0.08:
            return None

        felt_x, felt_y, felt_w, felt_h = cv2.boundingRect(contour)
        if felt_w <= 0 or felt_h <= 0:
            return None

        scale_x = felt_w / self.base_felt_w
        scale_y = felt_h / self.base_felt_h
        if scale_x <= 0 or scale_y <= 0:
            return None

        content_x = int(round(felt_x - self.base_felt_x * scale_x))
        content_y = int(round(felt_y - self.base_felt_y * scale_y))
        content_w = int(round(self.base_width * scale_x))
        content_h = int(round(self.base_height * scale_y))

        left = max(0, content_x)
        top = max(0, content_y)
        right = min(width, content_x + content_w)
        bottom = min(height, content_y + content_h)

        if right - left < width * 0.45 or bottom - top < height * 0.45:
            return None

        confidence = min(1.0, max(0.0, area / frame_area / 0.22))
        return TableContentRect(
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
            confidence=confidence,
        )


def normalize_table_frame(
    frame: np.ndarray,
    rect: WindowRect,
    *,
    enabled: bool = True,
) -> tuple[np.ndarray, WindowRect, Optional[TableContentRect]]:
    """Crop to detected table content when the selected window has extra chrome."""
    if not enabled:
        return frame, rect, None

    detected = PokerStarsTableLocator().locate(frame)
    if detected is None:
        return frame, rect, None

    # If detection is essentially the full selected window, keep the original
    # pixels to avoid introducing off-by-one jitter in already clean captures.
    horizontal_margin = detected.x + max(0, frame.shape[1] - (detected.x + detected.width))
    vertical_margin = detected.y + max(0, frame.shape[0] - (detected.y + detected.height))
    if horizontal_margin < 8 and vertical_margin < 16:
        return frame, rect, detected

    cropped = frame[
        detected.y : detected.y + detected.height,
        detected.x : detected.x + detected.width,
    ]
    return cropped, detected.as_window_rect(rect), detected
