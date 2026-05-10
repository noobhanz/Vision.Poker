#!/usr/bin/env python3
"""
vision.poker - Beautiful Graphical Setup Wizard

A polished, Apple-style installer experience.
"""

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)


class Colors:
    BG_DARK = "#0f0f17"
    BG_CARD = "#1a1a28"
    BG_CARD_HOVER = "#252538"
    ACCENT = "#00c853"
    ACCENT_DARK = "#00a040"
    TEXT = "#ffffff"
    TEXT_MUTED = "#8b8b9e"
    BORDER = "#2d2d42"


STYLESHEET = f"""
QWidget {{
    background-color: {Colors.BG_DARK};
    color: {Colors.TEXT};
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
}}

QLabel {{
    background: transparent;
}}

QLabel#title {{
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.5px;
}}

QLabel#subtitle {{
    font-size: 16px;
    color: {Colors.TEXT_MUTED};
    line-height: 1.6;
}}

QLabel#step-title {{
    font-size: 24px;
    font-weight: 600;
}}

QLabel#feature {{
    font-size: 15px;
    color: {Colors.TEXT_MUTED};
    padding: 8px 0;
}}

QLabel#feature-check {{
    color: {Colors.ACCENT};
    font-size: 18px;
}}

QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {Colors.ACCENT}, stop:1 #00e676);
    color: #000000;
    border: none;
    border-radius: 12px;
    padding: 16px 40px;
    font-size: 16px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00e676, stop:1 #69f0ae);
}}

QPushButton:pressed {{
    background: {Colors.ACCENT_DARK};
}}

QPushButton#secondary {{
    background: transparent;
    color: {Colors.TEXT_MUTED};
    border: 1px solid {Colors.BORDER};
}}

QPushButton#secondary:hover {{
    background: {Colors.BG_CARD};
    color: {Colors.TEXT};
    border-color: {Colors.TEXT_MUTED};
}}

QComboBox {{
    background: {Colors.BG_CARD};
    border: 2px solid {Colors.BORDER};
    border-radius: 12px;
    padding: 14px 20px;
    font-size: 15px;
    min-width: 280px;
}}

QComboBox:hover {{
    border-color: {Colors.ACCENT};
}}

QComboBox:focus {{
    border-color: {Colors.ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 20px;
}}

QComboBox QAbstractItemView {{
    background: {Colors.BG_CARD};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    selection-background-color: {Colors.ACCENT};
    selection-color: #000;
    padding: 8px;
}}

QRadioButton {{
    font-size: 15px;
    spacing: 12px;
    padding: 8px;
}}

QRadioButton::indicator {{
    width: 22px;
    height: 22px;
    border-radius: 11px;
    border: 2px solid {Colors.BORDER};
    background: {Colors.BG_CARD};
}}

QRadioButton::indicator:hover {{
    border-color: {Colors.ACCENT};
}}

QRadioButton::indicator:checked {{
    background: {Colors.ACCENT};
    border-color: {Colors.ACCENT};
}}

QCheckBox {{
    font-size: 15px;
    spacing: 12px;
    padding: 8px;
}}

QCheckBox::indicator {{
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 2px solid {Colors.BORDER};
    background: {Colors.BG_CARD};
}}

QCheckBox::indicator:hover {{
    border-color: {Colors.ACCENT};
}}

QCheckBox::indicator:checked {{
    background: {Colors.ACCENT};
    border-color: {Colors.ACCENT};
}}

QProgressBar {{
    background: {Colors.BG_CARD};
    border: none;
    border-radius: 8px;
    height: 16px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {Colors.ACCENT}, stop:1 #00e676);
    border-radius: 8px;
}}

QFrame#card {{
    background: {Colors.BG_CARD};
    border: 1px solid {Colors.BORDER};
    border-radius: 16px;
}}

QFrame#card:hover {{
    border-color: {Colors.ACCENT};
}}
"""


class AnimatedButton(QPushButton):
    """Button with hover animation."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 200, 83, 100))
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)

    def enterEvent(self, event):
        self.shadow.setBlurRadius(40)
        self.shadow.setColor(QColor(0, 200, 83, 150))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 200, 83, 100))
        super().leaveEvent(event)


class WelcomePage(QWidget):
    """Beautiful welcome page."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 80, 60, 60)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("V.P")
        logo.setStyleSheet(f"font-size: 48px; font-weight: 800; color: {Colors.ACCENT}; background: transparent;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        layout.addSpacing(30)

        # Title
        title = QLabel("Welcome to Vision")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(16)

        # Subtitle
        subtitle = QLabel("Real-time poker HUD that shows you equity,\npot odds, and EV as you play.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(50)

        # Features
        features = [
            ("✓", "Real-time equity calculation"),
            ("✓", "Pot odds & expected value"),
            ("✓", "Draw detection with outs"),
            ("✓", "Works with all major poker sites"),
        ]

        features_container = QWidget()
        features_layout = QVBoxLayout(features_container)
        features_layout.setSpacing(4)

        for icon_text, text in features:
            row = QHBoxLayout()
            row.setSpacing(12)

            icon_label = QLabel(icon_text)
            icon_label.setObjectName("feature-check")
            icon_label.setFixedWidth(30)
            row.addWidget(icon_label)

            text_label = QLabel(text)
            text_label.setObjectName("feature")
            row.addWidget(text_label)

            row.addStretch()
            features_layout.addLayout(row)

        layout.addWidget(features_container, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()


class ConfigPage(QWidget):
    """Configuration page."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(30)

        # Title
        title = QLabel("Quick Setup")
        title.setObjectName("step-title")
        layout.addWidget(title)

        subtitle = QLabel("Choose your poker client and preferences.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Poker client selection
        client_label = QLabel("Which poker client do you use?")
        client_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        layout.addWidget(client_label)

        self.client_combo = QComboBox()
        self.client_combo.addItems([
            "PokerStars",
            "GGPoker",
            "PartyPoker",
            "888poker",
            "WPT Global",
        ])
        layout.addWidget(self.client_combo)

        layout.addSpacing(20)

        # HUD Position
        pos_label = QLabel("Where should the HUD appear?")
        pos_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        layout.addWidget(pos_label)

        self.position_group = QButtonGroup()
        positions = [
            ("Top Right (Recommended)", "top-right"),
            ("Top Left", "top-left"),
            ("Bottom Right", "bottom-right"),
        ]

        for i, (label, value) in enumerate(positions):
            radio = QRadioButton(label)
            radio.setProperty("position", value)
            if i == 0:
                radio.setChecked(True)
            self.position_group.addButton(radio)
            layout.addWidget(radio)

        layout.addSpacing(20)

        # Launch options
        self.start_login = QCheckBox("Launch vision.poker when I log in")
        self.start_login.setChecked(True)
        layout.addWidget(self.start_login)

        layout.addStretch()

    def get_config(self):
        position = "top-right"
        for btn in self.position_group.buttons():
            if btn.isChecked():
                position = btn.property("position")
                break

        return {
            "poker_client_title": self.client_combo.currentText(),
            "hud_position": position,
            "start_at_login": self.start_login.isChecked(),
        }


class SetupPage(QWidget):
    """Final setup/progress page."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 80, 60, 60)
        layout.setSpacing(20)

        # Icon
        self.icon = QLabel("...")
        self.icon.setStyleSheet(f"font-size: 48px; font-weight: 800; color: {Colors.ACCENT}; background: transparent;")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon)

        layout.addSpacing(20)

        # Title
        self.title = QLabel("Setting Up...")
        self.title.setObjectName("step-title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        # Status
        self.status = QLabel("Configuring vision.poker")
        self.status.setObjectName("subtitle")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        layout.addSpacing(30)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress)

        layout.addStretch()

        self.config = {}

    def start_setup(self, config):
        self.config = config
        self.progress.setValue(0)

        # Animate progress
        self._step = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_progress)
        self._timer.start(50)

    def _update_progress(self):
        self._step += 1

        if self._step <= 30:
            self.status.setText("Creating configuration...")
            self.progress.setValue(self._step)
        elif self._step <= 60:
            self.status.setText("Setting up launch agent...")
            self.progress.setValue(self._step)
        elif self._step <= 90:
            self.status.setText("Finalizing...")
            self.progress.setValue(self._step)
        elif self._step <= 100:
            self.progress.setValue(self._step)
        else:
            self._timer.stop()
            self._save_config()
            self._setup_complete()

    def _save_config(self):
        project_dir = Path(__file__).parent.parent
        env_file = project_dir / ".env"

        content = f"""POKER_CLIENT_TITLE={self.config.get('poker_client_title', 'PokerStars')}
SKIN_CONFIG=pokerstars
CAPTURE_FPS=2
MONTE_CARLO_N=5000
HUD_HOTKEY=F9
HUD_OPACITY=0.88
HUD_POSITION={self.config.get('hud_position', 'top-right')}
DEBUG_MODE=false
"""
        with open(env_file, "w") as f:
            f.write(content)

    def _setup_complete(self):
        self.icon.setText("OK")
        self.title.setText("You're All Set!")
        self.status.setText("Vision is ready to go.")

        # Find the wizard window and show complete
        wizard = self.window()
        if hasattr(wizard, 'show_complete'):
            wizard.show_complete()


class CompletePage(QWidget):
    """Completion page."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 80, 60, 60)
        layout.setSpacing(20)

        # Logo
        logo = QLabel("V.P")
        logo.setStyleSheet(f"font-size: 48px; font-weight: 800; color: {Colors.ACCENT}; background: transparent;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        layout.addSpacing(20)

        # Title
        title = QLabel("You're All Set!")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(10)

        subtitle = QLabel("Vision has been configured successfully.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        # Quick start card
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 16px;
                padding: 24px;
            }}
        """)
        card_layout = QVBoxLayout(card)

        quick_title = QLabel("Quick Start")
        quick_title.setStyleSheet("font-weight: 600; font-size: 16px;")
        card_layout.addWidget(quick_title)

        steps = [
            "1. Look for V.P in your menu bar",
            "2. Click it and select 'Start HUD'",
            "3. Open your poker client",
            "4. Press F9 to toggle the overlay",
        ]

        for step in steps:
            step_label = QLabel(step)
            step_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 14px; padding: 4px 0;")
            card_layout.addWidget(step_label)

        layout.addWidget(card)

        layout.addStretch()


class SetupWizard(QWidget):
    """Main wizard window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("vision.poker Setup")
        self.setFixedSize(500, 650)
        self.setStyleSheet(STYLESHEET)

        # Remove window frame for cleaner look
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main container with rounded corners
        container = QFrame(self)
        container.setGeometry(0, 0, 500, 650)
        container.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_DARK};
                border-radius: 20px;
                border: 1px solid {Colors.BORDER};
            }}
        """)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 10)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                border: none;
                font-size: 24px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT};
            }}
        """)
        close_btn.clicked.connect(self.close)

        header = QHBoxLayout()
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Page stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Pages
        self.welcome_page = WelcomePage()
        self.config_page = ConfigPage()
        self.setup_page = SetupPage()
        self.complete_page = CompletePage()

        self.stack.addWidget(self.welcome_page)
        self.stack.addWidget(self.config_page)
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.complete_page)

        # Navigation buttons
        nav = QWidget()
        nav.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(40, 20, 40, 40)

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondary")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.hide()
        nav_layout.addWidget(self.back_btn)

        nav_layout.addStretch()

        self.next_btn = AnimatedButton("Get Started")
        self.next_btn.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_btn)

        layout.addWidget(nav)

        # For dragging window
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def go_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def go_next(self):
        idx = self.stack.currentIndex()

        if idx == 0:  # Welcome -> Config
            self.stack.setCurrentIndex(1)
        elif idx == 1:  # Config -> Setup
            config = self.config_page.get_config()
            self.stack.setCurrentIndex(2)
            self.setup_page.start_setup(config)
        elif idx == 3:  # Complete -> Launch
            self._launch_app()
            self.close()

        self._update_nav()

    def show_complete(self):
        self.stack.setCurrentIndex(3)
        self._update_nav()

    def _update_nav(self):
        idx = self.stack.currentIndex()

        self.back_btn.setVisible(idx == 1)

        if idx == 0:
            self.next_btn.setText("Get Started")
            self.next_btn.show()
        elif idx == 1:
            self.next_btn.setText("Continue")
            self.next_btn.show()
        elif idx == 2:
            self.next_btn.hide()
        elif idx == 3:
            self.next_btn.setText("Launch vision.poker")
            self.next_btn.show()

    def _launch_app(self):
        project_dir = Path(__file__).parent.parent
        subprocess.Popen(
            [sys.executable, str(project_dir / "app.py")],
            cwd=str(project_dir),
            start_new_session=True,
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("vision.poker Setup")

    wizard = SetupWizard()
    wizard.show()

    # Center on screen
    screen = app.primaryScreen().geometry()
    wizard.move(
        (screen.width() - wizard.width()) // 2,
        (screen.height() - wizard.height()) // 2
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
