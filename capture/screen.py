"""
Capture a single frame from the poker client window.
Uses mss for cross-platform screen capture.
Targets the poker window by handle (not full screen).
Returns: np.ndarray (BGR, uint8)
Capture rate: configurable, default 2fps
"""

import asyncio
from typing import AsyncGenerator, Callable, Optional

import mss
import numpy as np

from .window_finder import WindowRect, find_poker_window


def capture_window(rect: WindowRect) -> np.ndarray:
    """
    Capture a screenshot of the specified window region.

    Args:
        rect: WindowRect specifying the region to capture

    Returns:
        np.ndarray in BGR format (uint8), compatible with OpenCV
    """
    with mss.mss() as sct:
        # Capture the region
        screenshot = sct.grab(rect.mss_monitor)

        # Convert to numpy array (BGRA format from mss)
        img = np.array(screenshot)

        # Convert BGRA to BGR (drop alpha channel)
        img_bgr = img[:, :, :3]

        return img_bgr


def capture_full_screen() -> np.ndarray:
    """
    Capture the entire primary screen.

    Returns:
        np.ndarray in BGR format (uint8)
    """
    with mss.mss() as sct:
        # Use the first monitor (primary screen)
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        return img[:, :, :3]


async def capture_loop(
    title_substring: str,
    fps: float = 2.0,
    on_frame: Optional[Callable[[np.ndarray, WindowRect], None]] = None,
) -> AsyncGenerator[tuple[np.ndarray, WindowRect], None]:
    """
    Async generator that yields frames from the poker window at specified FPS.

    Args:
        title_substring: Window title to search for
        fps: Frames per second to capture (default 2)
        on_frame: Optional callback called with each frame

    Yields:
        Tuple of (frame as np.ndarray BGR, WindowRect of capture region)

    Usage:
        async for frame, rect in capture_loop("PokerStars", fps=2):
            process_frame(frame)
    """
    interval = 1.0 / fps

    while True:
        # Find the window each iteration (handles window moves/resizes)
        rect = find_poker_window(title_substring)

        if rect is None:
            # Window not found, wait and retry
            await asyncio.sleep(interval)
            continue

        if rect.width <= 0 or rect.height <= 0:
            # Invalid window dimensions
            await asyncio.sleep(interval)
            continue

        try:
            frame = capture_window(rect)

            if on_frame:
                on_frame(frame, rect)

            yield frame, rect

        except Exception as e:
            # Handle capture errors gracefully
            print(f"Capture error: {e}")

        await asyncio.sleep(interval)


class ScreenCapture:
    """
    Synchronous screen capture class for simpler usage patterns.
    """

    def __init__(self, title_substring: str):
        """
        Initialize screen capture for a window.

        Args:
            title_substring: Part of window title to search for
        """
        self.title_substring = title_substring
        self._last_rect: Optional[WindowRect] = None

    def find_window(self) -> Optional[WindowRect]:
        """Find and cache the poker window rect."""
        self._last_rect = find_poker_window(self.title_substring)
        return self._last_rect

    def capture(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the poker window.

        Returns:
            np.ndarray BGR image if window found, None otherwise
        """
        rect = self.find_window()
        if rect is None:
            return None

        if rect.width <= 0 or rect.height <= 0:
            return None

        return capture_window(rect)

    @property
    def last_rect(self) -> Optional[WindowRect]:
        """Get the last captured window rect."""
        return self._last_rect
