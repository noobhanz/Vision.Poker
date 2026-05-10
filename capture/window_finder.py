"""Locate poker client window by title - platform-specific implementations."""

import platform
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowRect:
    """Rectangle representing window position and size."""

    x: int
    y: int
    width: int
    height: int

    @property
    def region(self) -> tuple[int, int, int, int]:
        """Return as (x, y, width, height) tuple for mss."""
        return (self.x, self.y, self.width, self.height)

    @property
    def mss_monitor(self) -> dict:
        """Return as mss monitor dict format."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


def find_poker_window(title_substring: str) -> Optional[WindowRect]:
    """
    Find a window by title substring.

    Args:
        title_substring: Part of the window title to search for

    Returns:
        WindowRect if found, None otherwise

    Platform-specific implementations:
    - Windows: pygetwindow
    - macOS: Quartz CGWindowListCopyWindowInfo
    - Linux: xdotool via subprocess
    """
    system = platform.system()

    if system == "Windows":
        return _find_window_windows(title_substring)
    elif system == "Darwin":
        return _find_window_macos(title_substring)
    elif system == "Linux":
        return _find_window_linux(title_substring)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def _find_window_windows(title_substring: str) -> Optional[WindowRect]:
    """Find window on Windows using pygetwindow."""
    try:
        import pygetwindow as gw

        windows = gw.getWindowsWithTitle(title_substring)
        if not windows:
            return None

        win = windows[0]
        return WindowRect(
            x=win.left,
            y=win.top,
            width=win.width,
            height=win.height,
        )
    except ImportError:
        print("pygetwindow not installed. Run: pip install pygetwindow", file=sys.stderr)
        return None


def _find_window_macos(title_substring: str) -> Optional[WindowRect]:
    """Find window on macOS using Quartz."""
    try:
        import Quartz

        # Get list of all windows
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )

        for window in window_list:
            # Get window name
            name = window.get(Quartz.kCGWindowName, "")
            owner = window.get(Quartz.kCGWindowOwnerName, "")

            # Check if title matches
            if title_substring.lower() in (name or "").lower() or title_substring.lower() in (owner or "").lower():
                bounds = window.get(Quartz.kCGWindowBounds, {})
                if bounds:
                    return WindowRect(
                        x=int(bounds.get("X", 0)),
                        y=int(bounds.get("Y", 0)),
                        width=int(bounds.get("Width", 0)),
                        height=int(bounds.get("Height", 0)),
                    )
        return None
    except ImportError:
        print("Quartz not available. Install pyobjc: pip install pyobjc-framework-Quartz", file=sys.stderr)
        return None


def _find_window_linux(title_substring: str) -> Optional[WindowRect]:
    """Find window on Linux using xdotool."""
    import subprocess

    try:
        # Find window ID by name
        result = subprocess.run(
            ["xdotool", "search", "--name", title_substring],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None

        # Get first matching window ID
        window_id = result.stdout.strip().split("\n")[0]

        # Get window geometry
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

        # Parse geometry output
        geometry = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                geometry[key] = int(value)

        return WindowRect(
            x=geometry.get("X", 0),
            y=geometry.get("Y", 0),
            width=geometry.get("WIDTH", 0),
            height=geometry.get("HEIGHT", 0),
        )
    except FileNotFoundError:
        print("xdotool not found. Install with: sudo apt install xdotool", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        return None


def list_windows() -> list[tuple[str, str]]:
    """
    List all visible windows for debugging.

    Returns:
        List of (owner_name, window_name) tuples
    """
    system = platform.system()

    if system == "Darwin":
        try:
            import Quartz

            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID,
            )

            results = []
            for window in window_list:
                owner = window.get(Quartz.kCGWindowOwnerName, "")
                name = window.get(Quartz.kCGWindowName, "")
                if owner or name:
                    results.append((owner, name))
            return results
        except ImportError:
            return []

    elif system == "Windows":
        try:
            import pygetwindow as gw

            return [(w.title, w.title) for w in gw.getAllWindows() if w.title]
        except ImportError:
            return []

    return []
