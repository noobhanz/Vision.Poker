"""Locate poker client window by title - platform-specific implementations."""

import platform
import sys
from dataclasses import dataclass
from typing import Optional


# Known poker client identifiers (app names / window title patterns)
POKER_CLIENTS = [
    "pokerstars",
    "ggpoker",
    "partypoker",
    "888poker",
    "wpt global",
    "winamax",
    "ignition",
    "bovada",
    "acr",
    "americas cardroom",
    "natural8",
    "betonline",
]


@dataclass
class WindowRect:
    """Rectangle representing window position and size."""

    x: int
    y: int
    width: int
    height: int
    window_id: Optional[int] = None
    title: Optional[str] = None

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


def _is_poker_client(owner: str, name: str) -> bool:
    """Check if window belongs to a known poker client."""
    combined = f"{owner} {name}".lower()
    return any(client in combined for client in POKER_CLIENTS)


def find_active_poker_window() -> Optional[WindowRect]:
    """
    Find the currently focused/frontmost poker window.

    This enables multi-table support: the HUD follows whichever
    poker table the user is currently looking at.

    Returns:
        WindowRect of the active poker window, or None if no poker window is focused
    """
    system = platform.system()

    if system == "Darwin":
        return _find_active_window_macos()
    elif system == "Windows":
        return _find_active_window_windows()
    elif system == "Linux":
        return _find_active_window_linux()
    else:
        return None


def _find_active_window_macos() -> Optional[WindowRect]:
    """Find the frontmost poker window on macOS."""
    try:
        import Quartz
        from AppKit import NSWorkspace

        # Get the frontmost application
        workspace = NSWorkspace.sharedWorkspace()
        frontmost_app = workspace.frontmostApplication()
        frontmost_name = frontmost_app.localizedName() if frontmost_app else ""

        # Check if it's a poker client
        if not any(client in frontmost_name.lower() for client in POKER_CLIENTS):
            return None

        # Get windows for this app (ordered front to back)
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )

        # Find the frontmost window from this app
        for window in window_list:
            owner = window.get(Quartz.kCGWindowOwnerName, "")
            if owner.lower() == frontmost_name.lower():
                bounds = window.get(Quartz.kCGWindowBounds, {})
                window_id = window.get(Quartz.kCGWindowNumber)
                name = window.get(Quartz.kCGWindowName, "")

                if bounds and bounds.get("Width", 0) > 100:  # Skip tiny windows
                    return WindowRect(
                        x=int(bounds.get("X", 0)),
                        y=int(bounds.get("Y", 0)),
                        width=int(bounds.get("Width", 0)),
                        height=int(bounds.get("Height", 0)),
                        window_id=window_id,
                        title=name,
                    )
        return None
    except ImportError:
        return None


def _find_active_window_windows() -> Optional[WindowRect]:
    """Find the frontmost poker window on Windows."""
    try:
        import pygetwindow as gw

        # Get the active window
        active = gw.getActiveWindow()
        if active is None:
            return None

        # Check if it's a poker client
        if not any(client in active.title.lower() for client in POKER_CLIENTS):
            return None

        return WindowRect(
            x=active.left,
            y=active.top,
            width=active.width,
            height=active.height,
            title=active.title,
        )
    except ImportError:
        return None


def _find_active_window_linux() -> Optional[WindowRect]:
    """Find the frontmost poker window on Linux."""
    import subprocess

    try:
        # Get active window ID
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

        window_id = result.stdout.strip()

        # Get window name
        name_result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True,
            text=True,
            timeout=5,
        )

        window_name = name_result.stdout.strip() if name_result.returncode == 0 else ""

        # Check if it's a poker client
        if not any(client in window_name.lower() for client in POKER_CLIENTS):
            return None

        # Get window geometry
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

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
            window_id=int(window_id),
            title=window_name,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def find_all_poker_windows() -> list[WindowRect]:
    """
    Find all open poker client windows.

    Returns:
        List of WindowRect for all detected poker windows
    """
    system = platform.system()
    results = []

    if system == "Darwin":
        try:
            import Quartz

            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID,
            )

            for window in window_list:
                owner = window.get(Quartz.kCGWindowOwnerName, "")
                name = window.get(Quartz.kCGWindowName, "")

                if _is_poker_client(owner, name):
                    bounds = window.get(Quartz.kCGWindowBounds, {})
                    window_id = window.get(Quartz.kCGWindowNumber)

                    if bounds and bounds.get("Width", 0) > 100:
                        results.append(WindowRect(
                            x=int(bounds.get("X", 0)),
                            y=int(bounds.get("Y", 0)),
                            width=int(bounds.get("Width", 0)),
                            height=int(bounds.get("Height", 0)),
                            window_id=window_id,
                            title=name,
                        ))
        except ImportError:
            pass

    elif system == "Windows":
        try:
            import pygetwindow as gw

            for win in gw.getAllWindows():
                if win.title and _is_poker_client(win.title, win.title):
                    results.append(WindowRect(
                        x=win.left,
                        y=win.top,
                        width=win.width,
                        height=win.height,
                        title=win.title,
                    ))
        except ImportError:
            pass

    return results
