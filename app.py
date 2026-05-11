#!/usr/bin/env python3
"""
vision.poker - macOS Menu Bar App

Runs as a menu bar status item like Magnet or Flux.
Click the icon to access controls, toggle HUD, change settings.
"""

import asyncio
import sys
import threading
from pathlib import Path

# Check for rumps (macOS menu bar library)
try:
    import rumps
    RUMPS_AVAILABLE = True
except ImportError:
    RUMPS_AVAILABLE = False

from config.settings import Settings
from capture.window_finder import find_poker_window, list_windows
from licensing.validator import LicenseValidator, LicenseStatus


class PokerVisionApp(rumps.App):
    """Menu bar application for vision.poker overlay."""

    def __init__(self, license_validator: LicenseValidator):
        super().__init__(
            "Vision Poker",
            icon=None,
            title="V.P",  # Clean text logo in menu bar
            quit_button=None,
        )

        self.settings = Settings()
        self.license_validator = license_validator
        self.pipeline = None
        self.pipeline_thread = None
        self.hud = None
        self.is_running = False
        self.license_valid = True

        # Build menu
        self.menu = [
            rumps.MenuItem("Start HUD", callback=self.toggle_hud),
            None,  # Separator
            rumps.MenuItem("Status: Stopped", callback=None),
            rumps.MenuItem("Window: Not detected", callback=None),
            rumps.MenuItem("License: Checking...", callback=None),
            None,  # Separator
            self._build_window_menu(),
            self._build_position_menu(),
            None,  # Separator
            rumps.MenuItem("Settings...", callback=self.open_settings),
            rumps.MenuItem("Detect Windows", callback=self.detect_windows),
            rumps.MenuItem("Manage Subscription...", callback=self.manage_subscription),
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Make status items non-clickable
        self.menu["Status: Stopped"].set_callback(None)
        self.menu["Window: Not detected"].set_callback(None)
        self.menu["License: Checking..."].set_callback(None)

        # Start periodic license check
        self._start_license_check_timer()

    def _build_window_menu(self):
        """Build submenu for window selection."""
        window_menu = rumps.MenuItem("Poker Window")

        # Add common poker clients
        clients = ["PokerStars", "GGPoker", "PartyPoker", "888poker", "WPT Global"]
        for client in clients:
            item = rumps.MenuItem(client, callback=self.select_window)
            if client == self.settings.poker_client_title:
                item.state = 1  # Checkmark
            window_menu.add(item)

        window_menu.add(None)  # Separator
        window_menu.add(rumps.MenuItem("Custom...", callback=self.custom_window))

        return window_menu

    def _build_position_menu(self):
        """Build submenu for HUD position."""
        position_menu = rumps.MenuItem("HUD Position")

        positions = [
            ("Top Right", "top-right"),
            ("Top Left", "top-left"),
            ("Bottom Right", "bottom-right"),
            ("Bottom Left", "bottom-left"),
        ]

        for label, value in positions:
            item = rumps.MenuItem(label, callback=self.select_position)
            if value == self.settings.hud_position:
                item.state = 1
            position_menu.add(item)

        return position_menu

    def _update_status(self, status: str, window: str = None):
        """Update status display in menu."""
        self.menu["Status: Stopped"].title = f"Status: {status}"
        if window:
            self.menu["Window: Not detected"].title = f"Window: {window}"

    @rumps.clicked("Start HUD")
    def toggle_hud(self, sender):
        """Toggle the HUD on/off."""
        if self.is_running:
            self.stop_hud()
            sender.title = "Start HUD"
            self.title = "V.P"
            self._update_status("Stopped")
        else:
            # Check license before starting
            if not self.license_valid:
                result = self.license_validator.validate()
                if not result.can_run:
                    rumps.alert(
                        title="Subscription Required",
                        message=result.message + "\n\nClick 'Manage Subscription' to subscribe.",
                    )
                    return
                self.license_valid = True

            success = self.start_hud()
            if success:
                sender.title = "Stop HUD"
                self.title = "V.P+"  # Active indicator
                self._update_status("Running", self.settings.poker_client_title)
            else:
                rumps.alert(
                    title="Window Not Found",
                    message=f"Could not find window: {self.settings.poker_client_title}\n\nMake sure the poker client is open.",
                )

    def start_hud(self) -> bool:
        """Start the HUD pipeline."""
        # Check if window exists
        rect = find_poker_window(self.settings.poker_client_title)
        if rect is None:
            return False

        # Import here to avoid slow startup
        from pipeline.runner import PipelineRunner
        from overlay.hud import create_hud_app

        # Create Qt app and HUD
        from PyQt6.QtWidgets import QApplication
        self.qt_app = QApplication.instance()
        if self.qt_app is None:
            self.qt_app = QApplication([])

        from overlay.hud import PokerHUD
        self.hud = PokerHUD(
            hotkey=self.settings.hud_hotkey,
            opacity=self.settings.hud_opacity,
            position=self.settings.hud_position,
        )

        # Create pipeline
        self.pipeline = PipelineRunner(self.settings)
        self.pipeline.connect_hud(self.hud)

        # Run pipeline in background thread
        def run_pipeline():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pipeline.run())
            except Exception as e:
                print(f"Pipeline error: {e}")
            finally:
                loop.close()

        self.pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        self.pipeline_thread.start()

        # Show HUD
        self.hud.show()

        # Process Qt events in rumps timer
        self._start_qt_timer()

        self.is_running = True
        return True

    def _start_qt_timer(self):
        """Start a timer to process Qt events."""
        def process_qt():
            if self.qt_app and self.is_running:
                self.qt_app.processEvents()

        self.qt_timer = rumps.Timer(process_qt, 0.05)  # 50ms
        self.qt_timer.start()

    def stop_hud(self):
        """Stop the HUD pipeline."""
        self.is_running = False

        if hasattr(self, 'qt_timer'):
            self.qt_timer.stop()

        if self.pipeline:
            self.pipeline.stop()
            self.pipeline = None

        if self.hud:
            self.hud.hide()
            self.hud = None

    def select_window(self, sender):
        """Handle window selection."""
        # Uncheck all items in the menu
        for item in self.menu["Poker Window"].values():
            if hasattr(item, 'state'):
                item.state = 0

        # Check selected item
        sender.state = 1

        # Update settings
        self.settings.poker_client_title = sender.title

        # Restart if running
        if self.is_running:
            self.stop_hud()
            self.start_hud()

    def custom_window(self, sender):
        """Prompt for custom window title."""
        response = rumps.Window(
            title="Custom Window Title",
            message="Enter the poker client window title:",
            default_text=self.settings.poker_client_title,
            ok="Set",
            cancel="Cancel",
        ).run()

        if response.clicked:
            self.settings.poker_client_title = response.text
            self._update_status("Stopped", response.text)

    def select_position(self, sender):
        """Handle position selection."""
        # Uncheck all items
        for item in self.menu["HUD Position"].values():
            if hasattr(item, 'state'):
                item.state = 0

        sender.state = 1

        # Map label to value
        position_map = {
            "Top Right": "top-right",
            "Top Left": "top-left",
            "Bottom Right": "bottom-right",
            "Bottom Left": "bottom-left",
        }

        self.settings.hud_position = position_map.get(sender.title, "top-right")

        # Update HUD position if running
        if self.hud:
            self.hud.position_preference = self.settings.hud_position

    def detect_windows(self, sender):
        """Show detected windows."""
        windows = list_windows()

        if not windows:
            rumps.alert(
                title="No Windows Found",
                message="Could not detect any windows.\n\nMake sure the poker client is open and visible.",
            )
            return

        # Format window list
        window_list = "\n".join([f"• {owner}: {name}" for owner, name in windows[:20]])

        rumps.alert(
            title="Detected Windows",
            message=f"Found {len(windows)} windows:\n\n{window_list}",
        )

    def open_settings(self, sender):
        """Open settings (placeholder)."""
        rumps.alert(
            title="Settings",
            message=f"Current settings:\n\n"
                    f"Window: {self.settings.poker_client_title}\n"
                    f"Skin: {self.settings.skin_config}\n"
                    f"FPS: {self.settings.capture_fps}\n"
                    f"Hotkey: {self.settings.hud_hotkey}\n"
                    f"Position: {self.settings.hud_position}\n\n"
                    f"Edit .env file to change settings.",
        )

    def quit_app(self, sender):
        """Quit the application."""
        self.stop_hud()
        rumps.quit_application()

    def _start_license_check_timer(self):
        """Start periodic license validation (every hour)."""
        def check_license():
            self._validate_license()

        # Check every hour
        self.license_timer = rumps.Timer(check_license, 3600)
        self.license_timer.start()

        # Initial check
        self._validate_license()

    def _validate_license(self):
        """Validate license and update UI."""
        result = self.license_validator.validate()

        if result.status == LicenseStatus.VALID:
            self.menu["License: Checking..."].title = "License: Active"
            self.license_valid = True
        elif result.status == LicenseStatus.TRIAL:
            self.menu["License: Checking..."].title = f"License: Trial ({result.days_remaining} days left)"
            self.license_valid = True
        elif result.status == LicenseStatus.TRIAL_EXPIRING:
            self.menu["License: Checking..."].title = f"License: Trial ending ({result.days_remaining} days)"
            self.license_valid = True
            # Show reminder notification
            rumps.notification(
                title="Vision Poker",
                subtitle="Trial Ending Soon",
                message=f"Your trial ends in {result.days_remaining} days. Subscribe to continue.",
            )
        elif result.status == LicenseStatus.NETWORK_ERROR:
            self.menu["License: Checking..."].title = "License: Offline mode"
            self.license_valid = True  # Allow brief offline usage
        else:
            # Expired, invalid, or payment required
            self.menu["License: Checking..."].title = "License: Expired"
            self.license_valid = False

            # Stop HUD if running
            if self.is_running:
                self.stop_hud()
                self.menu["Start HUD"].title = "Start HUD"
                self.title = "V.P"
                self._update_status("Stopped")

            # Show payment notification
            rumps.notification(
                title="Vision Poker",
                subtitle="Subscription Required",
                message=result.message,
            )

    def manage_subscription(self, sender):
        """Open subscription management in browser."""
        import webbrowser

        # Try to get portal URL
        license_key = self.license_validator.license_key
        if license_key:
            # Open customer portal or checkout
            result = self.license_validator.validate()
            if result.checkout_url:
                webbrowser.open(result.checkout_url)
            else:
                webbrowser.open("https://vision.poker/#pricing")
        else:
            webbrowser.open("https://vision.poker/#pricing")


def check_license_startup() -> tuple[LicenseValidator, bool]:
    """
    Check license on startup and show appropriate dialogs.

    Returns:
        Tuple of (validator, can_run)
    """
    from PyQt6.QtWidgets import QApplication

    validator = LicenseValidator()

    # Create Qt app for dialogs
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication([])

    # Check if we have a stored license
    if not validator.has_license:
        # Show license entry dialog
        from licensing.dialogs import LicenseEntryDialog

        dialog = LicenseEntryDialog(validator)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return validator, False

    # Validate the license
    result = validator.validate()

    if result.can_run:
        # Check if trial is expiring and show reminder
        if result.status == LicenseStatus.TRIAL_EXPIRING:
            from licensing.dialogs import PaymentRequiredDialog

            dialog = PaymentRequiredDialog(validator, result)
            dialog.exec()  # Non-blocking, user can continue

        return validator, True
    else:
        # License not valid - show payment dialog
        from licensing.dialogs import TrialExpiredDialog

        dialog = TrialExpiredDialog(validator, result)
        dialog.exec()
        return validator, False


def main():
    """Entry point for menu bar app."""
    if not RUMPS_AVAILABLE:
        print("Error: rumps not installed")
        print("Install with: pip install rumps")
        print("")
        print("Falling back to command-line mode...")
        from pipeline.runner import main as cli_main
        cli_main()
        return

    # Check license before starting
    validator, can_run = check_license_startup()

    if not can_run:
        print("License validation failed. Exiting.")
        sys.exit(1)

    # Run the menu bar app
    app = PokerVisionApp(license_validator=validator)
    app.run()


if __name__ == "__main__":
    main()
