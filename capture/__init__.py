"""Screen capture module for poker client window capture."""

from .window_finder import find_poker_window, WindowRect
from .screen import capture_window, capture_loop
from .frame_buffer import FrameBuffer

__all__ = [
    "find_poker_window",
    "WindowRect",
    "capture_window",
    "capture_loop",
    "FrameBuffer",
]
