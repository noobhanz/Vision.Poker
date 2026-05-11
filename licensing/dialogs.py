"""License dialogs for activation and payment prompts."""

from typing import Optional, Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from .validator import LicenseValidator, LicenseStatus, ValidationResult


class Colors:
    """UI colors matching the app theme."""
    BG = "#0f0f17"
    BG_CARD = "#1a1a28"
    ACCENT = "#00c853"
    ACCENT_HOVER = "#00e676"
    TEXT = "#ffffff"
    TEXT_MUTED = "#8b8b9e"
    BORDER = "#2d2d42"
    ERROR = "#f44336"
    WARNING = "#ffab00"


DIALOG_STYLE = f"""
QDialog {{
    background-color: {Colors.BG};
    color: {Colors.TEXT};
}}
QLabel {{
    color: {Colors.TEXT};
    background: transparent;
}}
QLabel#title {{
    font-size: 24px;
    font-weight: 700;
}}
QLabel#subtitle {{
    color: {Colors.TEXT_MUTED};
    font-size: 14px;
}}
QLabel#error {{
    color: {Colors.ERROR};
    font-size: 12px;
}}
QLabel#warning {{
    color: {Colors.WARNING};
    font-size: 13px;
}}
QLineEdit {{
    background-color: {Colors.BG_CARD};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 16px;
    font-family: 'SF Mono', Monaco, monospace;
    color: {Colors.TEXT};
    letter-spacing: 2px;
}}
QLineEdit:focus {{
    border-color: {Colors.ACCENT};
}}
QPushButton {{
    background-color: {Colors.ACCENT};
    color: #000000;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {Colors.ACCENT_HOVER};
}}
QPushButton:disabled {{
    background-color: {Colors.BORDER};
    color: {Colors.TEXT_MUTED};
}}
QPushButton#secondary {{
    background-color: transparent;
    color: {Colors.TEXT_MUTED};
    border: 1px solid {Colors.BORDER};
}}
QPushButton#secondary:hover {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT};
}}
QFrame#separator {{
    background-color: {Colors.BORDER};
    max-height: 1px;
}}
"""


class LicenseEntryDialog(QDialog):
    """Dialog for entering a license key."""

    def __init__(self, validator: LicenseValidator, parent=None):
        super().__init__(parent)
        self.validator = validator
        self.result: Optional[ValidationResult] = None

        self.setWindowTitle("vision.poker - Activate License")
        self.setFixedSize(440, 320)
        self.setStyleSheet(DIALOG_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Logo
        logo = QLabel("V.P")
        logo.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {Colors.ACCENT};")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Title
        title = QLabel("Enter Your License Key")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Find your key in the email we sent after signup")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # License input
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.license_input.setMaxLength(19)  # 16 chars + 3 dashes
        self.license_input.textChanged.connect(self._format_license_key)
        layout.addWidget(self.license_input)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.clicked.connect(self._activate)
        self.activate_btn.setEnabled(False)
        btn_layout.addWidget(self.activate_btn)

        layout.addLayout(btn_layout)

        # Get license link
        get_license = QLabel('<a href="https://vision.poker/#pricing" style="color: #00c853;">Don\'t have a license? Start free trial</a>')
        get_license.setOpenExternalLinks(True)
        get_license.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(get_license)

    def _format_license_key(self, text: str):
        """Auto-format license key with dashes."""
        # Remove existing dashes and convert to uppercase
        clean = text.replace("-", "").upper()

        # Only allow alphanumeric
        clean = "".join(c for c in clean if c.isalnum())

        # Limit to 16 characters
        clean = clean[:16]

        # Add dashes every 4 characters
        formatted = "-".join(clean[i:i+4] for i in range(0, len(clean), 4))

        # Update input without triggering recursion
        if formatted != text:
            self.license_input.blockSignals(True)
            self.license_input.setText(formatted)
            self.license_input.blockSignals(False)

        # Enable button if we have a full key
        self.activate_btn.setEnabled(len(clean) == 16)

    def _activate(self):
        """Attempt to activate the license."""
        license_key = self.license_input.text().strip()
        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Activating...")

        # Validate
        self.result = self.validator.activate(license_key)

        if self.result.can_run:
            self.accept()
        else:
            self.error_label.setText(self.result.message)
            self.error_label.show()
            self.activate_btn.setText("Activate")
            self.activate_btn.setEnabled(True)


class PaymentRequiredDialog(QDialog):
    """Dialog shown when trial expires or payment fails."""

    def __init__(
        self,
        validator: LicenseValidator,
        validation_result: ValidationResult,
        parent=None
    ):
        super().__init__(parent)
        self.validator = validator
        self.validation_result = validation_result

        self.setWindowTitle("vision.poker - Subscription Required")
        self.setFixedSize(480, 400)
        self.setStyleSheet(DIALOG_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Logo
        logo = QLabel("V.P")
        logo.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {Colors.ACCENT};")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Title based on status
        if self.validation_result.status == LicenseStatus.TRIAL_EXPIRING:
            title_text = "Trial Ending Soon"
            message = f"Your trial ends in {self.validation_result.days_remaining} day{'s' if self.validation_result.days_remaining != 1 else ''}.\nSubscribe now to keep using Vision Poker."
        elif self.validation_result.status == LicenseStatus.PAYMENT_REQUIRED:
            title_text = "Payment Required"
            message = "Your trial has ended.\nSubscribe to continue using Vision Poker."
        else:
            title_text = "Subscription Expired"
            message = "Your subscription has expired.\nPlease renew to continue."

        title = QLabel(title_text)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        msg = QLabel(message)
        msg.setObjectName("subtitle")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        layout.addSpacing(16)

        # Pricing options
        pricing_frame = QFrame()
        pricing_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        pricing_layout = QVBoxLayout(pricing_frame)

        # Monthly option
        monthly_layout = QHBoxLayout()
        monthly_label = QLabel("Monthly")
        monthly_label.setStyleSheet("font-weight: 600;")
        monthly_price = QLabel("$36/month")
        monthly_price.setStyleSheet(f"color: {Colors.ACCENT}; font-weight: 700;")
        monthly_layout.addWidget(monthly_label)
        monthly_layout.addStretch()
        monthly_layout.addWidget(monthly_price)
        pricing_layout.addLayout(monthly_layout)

        # Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        pricing_layout.addWidget(sep)

        # Yearly option
        yearly_layout = QHBoxLayout()
        yearly_label = QLabel("Yearly")
        yearly_label.setStyleSheet("font-weight: 600;")
        yearly_price = QLabel("$360/year")
        yearly_price.setStyleSheet(f"color: {Colors.ACCENT}; font-weight: 700;")
        yearly_save = QLabel("(Save 2 months)")
        yearly_save.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")
        yearly_layout.addWidget(yearly_label)
        yearly_layout.addStretch()
        yearly_layout.addWidget(yearly_save)
        yearly_layout.addWidget(yearly_price)
        pricing_layout.addLayout(yearly_layout)

        layout.addWidget(pricing_frame)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # Subscribe monthly
        self.monthly_btn = QPushButton("Subscribe Monthly")
        self.monthly_btn.clicked.connect(lambda: self._subscribe("monthly"))
        btn_layout.addWidget(self.monthly_btn)

        # Subscribe yearly
        self.yearly_btn = QPushButton("Subscribe Yearly")
        self.yearly_btn.clicked.connect(lambda: self._subscribe("yearly"))
        btn_layout.addWidget(self.yearly_btn)

        layout.addLayout(btn_layout)

        # Continue trial button (if trial not expired)
        if self.validation_result.status == LicenseStatus.TRIAL_EXPIRING and self.validation_result.can_run:
            continue_btn = QPushButton("Continue Trial")
            continue_btn.setObjectName("secondary")
            continue_btn.clicked.connect(self.accept)
            layout.addWidget(continue_btn)

    def _subscribe(self, price_type: str):
        """Open checkout in browser."""
        if self.validation_result.checkout_url:
            import webbrowser
            webbrowser.open(self.validation_result.checkout_url)
        else:
            url = self.validator.get_checkout_url(price_type)
            if url:
                import webbrowser
                webbrowser.open(url)

        # Show message
        QMessageBox.information(
            self,
            "Complete Payment",
            "Complete your payment in the browser.\n\nOnce done, restart Vision Poker.",
        )


class TrialExpiredDialog(QDialog):
    """Dialog shown when trial is fully expired and app cannot run."""

    def __init__(
        self,
        validator: LicenseValidator,
        validation_result: ValidationResult,
        parent=None
    ):
        super().__init__(parent)
        self.validator = validator
        self.validation_result = validation_result

        self.setWindowTitle("vision.poker - Trial Expired")
        self.setFixedSize(440, 340)
        self.setStyleSheet(DIALOG_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Logo
        logo = QLabel("V.P")
        logo.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {Colors.ERROR};")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Title
        title = QLabel("Trial Expired")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Message
        msg = QLabel(self.validation_result.message)
        msg.setObjectName("subtitle")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        layout.addStretch()

        # Subscribe button
        subscribe_btn = QPushButton("Subscribe Now - $36/month")
        subscribe_btn.clicked.connect(self._subscribe)
        layout.addWidget(subscribe_btn)

        # Yearly option
        yearly_btn = QPushButton("Or $360/year (Save 2 months)")
        yearly_btn.setObjectName("secondary")
        yearly_btn.clicked.connect(lambda: self._subscribe("yearly"))
        layout.addWidget(yearly_btn)

        layout.addSpacing(8)

        # Quit button
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("secondary")
        quit_btn.clicked.connect(self.reject)
        layout.addWidget(quit_btn)

    def _subscribe(self, price_type: str = "monthly"):
        """Open checkout in browser."""
        if self.validation_result.checkout_url:
            import webbrowser
            webbrowser.open(self.validation_result.checkout_url)
        else:
            url = self.validator.get_checkout_url(price_type)
            if url:
                import webbrowser
                webbrowser.open(url)

        QMessageBox.information(
            self,
            "Complete Payment",
            "Complete your payment in the browser.\n\nOnce done, restart Vision Poker.",
        )
        self.reject()
