"""Individual metric display widgets for the HUD."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from engine.models import DrawType, Metrics


class MetricWidget(QWidget):
    """Widget displaying a single metric with label and value."""

    def __init__(self, label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.label_text = label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("metric_label")

        self.value = QLabel("--")
        self.value.setObjectName("metric_value")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.value)

    def set_value(self, text: str, style: str = "neutral") -> None:
        """
        Set the metric value with optional styling.

        Args:
            text: Value text to display
            style: One of "neutral", "positive", "negative", "warning"
        """
        self.value.setText(text)
        self.value.setObjectName(f"value_{style}")
        # Force style update
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)

    def set_percentage(self, value: float, threshold: Optional[float] = None) -> None:
        """
        Set value as percentage with automatic coloring.

        Args:
            value: Value between 0.0 and 1.0
            threshold: If provided, green if above, red if below
        """
        text = f"{value * 100:.1f}%"

        if threshold is not None:
            style = "positive" if value >= threshold else "negative"
        else:
            style = "neutral"

        self.set_value(text, style)

    def set_currency(self, value: float, positive_is_good: bool = True) -> None:
        """
        Set value as currency with sign and coloring.

        Args:
            value: Dollar/chip amount
            positive_is_good: Whether positive values should be green
        """
        sign = "+" if value >= 0 else ""
        text = f"{sign}${value:.2f}"

        if positive_is_good:
            style = "positive" if value >= 0 else "negative"
        else:
            style = "negative" if value >= 0 else "positive"

        self.set_value(text, style)


class RecommendationWidget(QFrame):
    """Widget displaying the action recommendation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("recommendation_box")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.arrow = QLabel("\u25b2")  # Up arrow
        self.text = QLabel("--")
        self.text.setObjectName("recommendation_text")

        self.reason = QLabel("")
        self.reason.setObjectName("metric_label")

        layout.addWidget(self.arrow)
        layout.addWidget(self.text)
        layout.addStretch()
        layout.addWidget(self.reason)

    def set_recommendation(self, rec: str, reason: str = "") -> None:
        """
        Set the recommendation display.

        Args:
            rec: "FOLD", "CALL", "RAISE CANDIDATE", or "WAIT"
            reason: Optional reason text
        """
        self.text.setText(rec)
        self.reason.setText(reason)

        if "WAIT" in rec:
            self.setObjectName("recommendation_box")
            self.text.setObjectName("recommendation_call")
            self.arrow.setText("\u25b6")  # Right arrow
        elif "FOLD" in rec:
            self.setObjectName("recommendation_box_fold")
            self.text.setObjectName("recommendation_fold")
            self.arrow.setText("\u25bc")  # Down arrow
        elif "RAISE" in rec:
            self.setObjectName("recommendation_box_raise")
            self.text.setObjectName("recommendation_raise")
            self.arrow.setText("\u25b2")  # Up arrow
        else:  # CALL
            self.setObjectName("recommendation_box")
            self.text.setObjectName("recommendation_call")
            self.arrow.setText("\u25b6")  # Right arrow

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)


class DrawInfoWidget(QWidget):
    """Widget displaying draw information."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.outs_label = QLabel("Outs: --")
        self.outs_label.setObjectName("draw_info")

        self.draw_type = QLabel("")
        self.draw_type.setObjectName("draw_info")

        layout.addWidget(self.outs_label)
        layout.addWidget(self.draw_type)
        layout.addStretch()

    def set_draw_info(self, outs: int, draw_type: DrawType) -> None:
        """Set draw information."""
        self.outs_label.setText(f"Outs: {outs}")

        draw_names = {
            DrawType.NONE: "",
            DrawType.FLUSH_DRAW: "Flush Draw",
            DrawType.OESD: "Open-Ended Straight",
            DrawType.GUTSHOT: "Gutshot",
            DrawType.COMBO_DRAW: "Combo Draw",
            DrawType.BACKDOOR_FLUSH: "Backdoor Flush",
        }

        self.draw_type.setText(draw_names.get(draw_type, ""))


class MadeHandWidget(QWidget):
    """Widget displaying made hand description."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.prefix = QLabel("Made hand:")
        self.prefix.setObjectName("metric_label")

        self.hand = QLabel("--")
        self.hand.setObjectName("made_hand")

        layout.addWidget(self.prefix)
        layout.addWidget(self.hand)
        layout.addStretch()

    def set_hand(self, description: str) -> None:
        """Set made hand description."""
        self.hand.setText(description)


class ConfidenceWidget(QWidget):
    """Widget displaying confidence and street info."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.confidence = QLabel("Confidence: --%")
        self.confidence.setObjectName("confidence")

        self.street = QLabel("PREFLOP")
        self.street.setObjectName("street_label")

        layout.addWidget(self.confidence)
        layout.addStretch()
        layout.addWidget(self.street)

    def set_info(self, confidence: float, street: str) -> None:
        """Set confidence and street display."""
        pct = int(confidence * 100)
        self.confidence.setText(f"Confidence: {pct}%")

        if confidence < 0.7:
            self.confidence.setObjectName("confidence_low")
        else:
            self.confidence.setObjectName("confidence")

        self.street.setText(street.upper())

        # Force style update
        self.confidence.style().unpolish(self.confidence)
        self.confidence.style().polish(self.confidence)
