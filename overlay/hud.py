"""
PyQt6 transparent frameless always-on-top overlay window.
Positions itself over the poker client window.
Updates metrics display in real time via Qt signals.
Click-through on Windows via WS_EX_TRANSPARENT extended style.
Does NOT intercept any mouse/keyboard input to the poker client.
"""

import platform
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from capture.window_finder import WindowRect
from engine.models import Metrics, Street

from .widgets import (
    ConfidenceWidget,
    DrawInfoWidget,
    MadeHandWidget,
    MetricWidget,
    RecommendationWidget,
)


class PokerHUD(QWidget):
    """
    Transparent always-on-top overlay HUD for poker metrics.
    """

    # Signal emitted when metrics should be updated
    metrics_updated = pyqtSignal(Metrics)

    def __init__(
        self,
        hotkey: str = "F9",
        opacity: float = 0.88,
        position: str = "top-right",
    ):
        super().__init__()

        self.hotkey = hotkey
        self.base_opacity = opacity
        self.position_preference = position
        self._poker_window_rect: Optional[WindowRect] = None

        self._setup_window()
        self._setup_ui()
        self._setup_hotkey()
        self._load_stylesheet()

        # Connect signal
        self.metrics_updated.connect(self._on_metrics_updated)

    def _setup_window(self) -> None:
        """Configure window flags for transparent overlay."""
        self.setWindowTitle("Vision Poker HUD")
        self.setObjectName("PokerHUD")

        # Window flags: frameless, always on top, tool window (no taskbar)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        # Platform-specific flags
        if platform.system() == "Darwin":
            # macOS: Use sheet window type for proper overlay behavior
            flags |= Qt.WindowType.Sheet
        elif platform.system() == "Windows":
            # Windows: Enable click-through
            self._enable_click_through_windows()

        self.setWindowFlags(flags)

        # Enable transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self.base_opacity)

        # Fixed width, height adjusts to content
        self.setFixedWidth(280)

    def _enable_click_through_windows(self) -> None:
        """Enable click-through on Windows using WS_EX_TRANSPARENT."""
        if platform.system() != "Windows":
            return

        try:
            import ctypes

            # Get window handle
            hwnd = int(self.winId())

            # Get current extended style
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000

            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # Add transparent and layered flags
            user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            )
        except Exception:
            pass  # Fail silently if ctypes not available

    def _setup_ui(self) -> None:
        """Build the HUD layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        self.title = QLabel("VISION.POKER")
        self.title.setObjectName("header")

        self.status = QLabel("\u25cf LIVE")
        self.status.setObjectName("status_live")

        self.hotkey_hint = QLabel(f"[{self.hotkey}:hide]")
        self.hotkey_hint.setObjectName("hotkey_hint")

        header_layout.addWidget(self.title)
        header_layout.addWidget(self.status)
        header_layout.addStretch()
        header_layout.addWidget(self.hotkey_hint)

        main_layout.addLayout(header_layout)

        # Separator
        sep1 = QFrame()
        sep1.setObjectName("separator")
        sep1.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep1)

        # Main metrics
        self.equity_widget = MetricWidget("Equity")
        self.pot_odds_widget = MetricWidget("Pot Odds")
        self.req_equity_widget = MetricWidget("Required Eq")
        self.ev_widget = MetricWidget("EV (call)")

        main_layout.addWidget(self.equity_widget)
        main_layout.addWidget(self.pot_odds_widget)
        main_layout.addWidget(self.req_equity_widget)
        main_layout.addWidget(self.ev_widget)

        # Separator
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep2)

        # Draw info
        self.draw_widget = DrawInfoWidget()
        main_layout.addWidget(self.draw_widget)

        # Made hand
        self.made_hand_widget = MadeHandWidget()
        main_layout.addWidget(self.made_hand_widget)

        # Separator
        sep3 = QFrame()
        sep3.setObjectName("separator")
        sep3.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep3)

        # Recommendation
        self.recommendation_widget = RecommendationWidget()
        main_layout.addWidget(self.recommendation_widget)

        # Separator
        sep4 = QFrame()
        sep4.setObjectName("separator")
        sep4.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep4)

        # Footer
        self.confidence_widget = ConfidenceWidget()
        main_layout.addWidget(self.confidence_widget)

    def _setup_hotkey(self) -> None:
        """Set up the toggle visibility hotkey."""
        shortcut = QShortcut(QKeySequence(self.hotkey), self)
        shortcut.activated.connect(self.toggle_visibility)

    def _load_stylesheet(self) -> None:
        """Load the QSS stylesheet."""
        style_path = Path(__file__).parent / "styles.qss"
        if style_path.exists():
            with open(style_path) as f:
                self.setStyleSheet(f.read())

    @pyqtSlot()
    def toggle_visibility(self) -> None:
        """Toggle HUD visibility without closing app."""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def position_over_window(self, rect: WindowRect) -> None:
        """
        Position the HUD relative to the poker window.

        Args:
            rect: WindowRect of the poker client
        """
        self._poker_window_rect = rect

        margin = 10
        hud_width = self.width()
        hud_height = self.height()

        if self.position_preference == "top-left":
            x = rect.x + margin
            y = rect.y + margin
        elif self.position_preference == "top-right":
            x = rect.x + rect.width - hud_width - margin
            y = rect.y + margin
        elif self.position_preference == "bottom-right":
            x = rect.x + rect.width - hud_width - margin
            y = rect.y + rect.height - hud_height - margin
        else:  # bottom-left
            x = rect.x + margin
            y = rect.y + rect.height - hud_height - margin

        self.move(x, y)

    def update_metrics(self, metrics: Metrics) -> None:
        """
        Update the HUD with new metrics.
        Thread-safe: emits signal for cross-thread updates.

        Args:
            metrics: Computed Metrics object
        """
        self.metrics_updated.emit(metrics)

    @pyqtSlot(Metrics)
    def _on_metrics_updated(self, metrics: Metrics) -> None:
        """Handle metrics update on the main thread."""
        # Update equity with comparison to required
        self.equity_widget.set_percentage(
            metrics.equity, threshold=metrics.required_equity
        )

        # Update pot odds
        self.pot_odds_widget.set_percentage(metrics.pot_odds)

        # Update required equity
        self.req_equity_widget.set_percentage(metrics.required_equity)

        # Update EV
        self.ev_widget.set_currency(metrics.ev_call)

        # Update draw info
        self.draw_widget.set_draw_info(metrics.outs, metrics.draw_type)

        # Update made hand
        self.made_hand_widget.set_hand(metrics.made_hand_rank)

        # Update recommendation
        reason = ""
        if metrics.recommendation == "WAIT":
            if metrics.action_mode == "preselect":
                reason = "(pre-action controls)"
            else:
                reason = "(no decision)"
        elif metrics.parse_status != "OK":
            reason = f"({metrics.parse_status.replace('_', ' ').lower()})"
        elif metrics.equity > metrics.required_equity:
            reason = "(equity > required)"
        elif metrics.equity < metrics.required_equity:
            reason = "(equity < required)"

        self.recommendation_widget.set_recommendation(metrics.recommendation, reason)

        # Update confidence and street
        street_name = metrics.street.value.upper()
        self.confidence_widget.set_info(metrics.confidence, street_name)

        # Update status indicator based on confidence
        if metrics.parse_status != "OK":
            self.status.setText(f"\u25cf {metrics.parse_status.replace('_', ' ')}")
            self.status.setObjectName("status_warning")
        elif metrics.confidence < 0.7:
            self.status.setText("\u25cf LOW CONF")
            self.status.setObjectName("status_warning")
        else:
            self.status.setText("\u25cf LIVE")
            self.status.setObjectName("status_live")

        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_status(self, status: str, is_warning: bool = False) -> None:
        """Set the status indicator."""
        self.status.setText(f"\u25cf {status}")
        self.status.setObjectName("status_warning" if is_warning else "status_live")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_street(self, street: Street) -> None:
        """Update the street display."""
        street_names = {
            Street.PREFLOP: "PREFLOP",
            Street.FLOP: "FLOP",
            Street.TURN: "TURN",
            Street.RIVER: "RIVER",
        }
        name = street_names.get(street, "PREFLOP")
        # Update via confidence widget
        if hasattr(self, "_last_confidence"):
            self.confidence_widget.set_info(self._last_confidence, name)


def create_hud_app(
    hotkey: str = "F9",
    opacity: float = 0.88,
    position: str = "top-right",
) -> tuple[QApplication, PokerHUD]:
    """
    Create and return the Qt application and HUD widget.

    Args:
        hotkey: Key to toggle visibility
        opacity: Window opacity (0.0-1.0)
        position: Position preference

    Returns:
        Tuple of (QApplication, PokerHUD)
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    hud = PokerHUD(hotkey=hotkey, opacity=opacity, position=position)
    return app, hud
