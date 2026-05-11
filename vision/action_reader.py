"""Read visible hero action buttons from a fixed poker table action area."""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .ocr_engine import OCREngine


@dataclass
class ActionState:
    """Current visible hero action state."""

    legal_actions: list[str] = field(default_factory=list)
    bet_to_call: Optional[float] = None
    action_amounts: dict[str, float] = field(default_factory=dict)
    mode: str = "none"
    preaction_count: int = 0
    confidence: float = 0.0


class ActionReader:
    """Classify PokerStars-style red action buttons inside a configured ROI."""

    def __init__(self, ocr_engine: Optional[OCREngine] = None):
        self.ocr_engine = ocr_engine or OCREngine()

    def read(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> ActionState:
        """Read legal actions and call amount from the action-button region."""
        x, y, w, h = roi
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return ActionState()
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            return ActionState()

        buttons = self._find_red_buttons(frame, roi)
        if len(buttons) < 2:
            checkbox_count = self._count_checkbox_prompts(frame, roi)
            if checkbox_count:
                return ActionState(
                    mode="preselect",
                    preaction_count=checkbox_count,
                    confidence=min(1.0, checkbox_count / 3),
                )
            return ActionState()

        if len(buttons) >= 3:
            button_rois = {
                "fold": buttons[0],
                "call_check": buttons[1],
                "raise_bet": buttons[2],
            }
        else:
            button_rois = {
                "call_check": buttons[0],
                "raise_bet": buttons[1],
            }

        legal_actions: list[str] = []
        action_amounts: dict[str, float] = {}
        bet_to_call: Optional[float] = None
        confidences = []

        fold_visible = (
            self._is_red_button(frame, button_rois["fold"])
            if "fold" in button_rois
            else 0.0
        )
        if fold_visible:
            legal_actions.append("fold")
            confidences.append(fold_visible)

        call_check_visible = self._is_red_button(frame, button_rois["call_check"])
        if call_check_visible:
            label = self._classify_call_or_check(frame, button_rois["call_check"])
            legal_actions.append(label)
            confidences.append(call_check_visible)
            if label == "call":
                amount = self.ocr_engine.read_number(
                    frame,
                    self._padded_roi(frame, button_rois["call_check"]),
                )
                if amount is not None and amount > 0:
                    bet_to_call = amount
                    action_amounts["call"] = amount
            else:
                bet_to_call = 0.0

        raise_bet_visible = self._is_red_button(frame, button_rois["raise_bet"])
        if raise_bet_visible:
            label = self._classify_raise_or_bet(frame, button_rois["raise_bet"])
            legal_actions.append(label)
            confidences.append(raise_bet_visible)
            amount = self.ocr_engine.read_number(
                frame,
                self._padded_roi(frame, button_rois["raise_bet"]),
            )
            if amount is not None and amount > 0:
                action_amounts[label] = amount

        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return ActionState(
            legal_actions=legal_actions,
            bet_to_call=bet_to_call,
            action_amounts=action_amounts,
            mode="decision",
            confidence=confidence,
        )

    def _padded_roi(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        """Pad contour-derived button boxes enough to keep tiny decimal dots."""
        x, y, w, h = roi
        x = max(0, x - 1)
        y = max(0, y)
        right = min(frame.shape[1], x + w + 3)
        bottom = min(frame.shape[0], y + h + 2)
        return (x, y, right - x, bottom - y)

    def _is_red_button(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> float:
        """Return red-button confidence, or 0.0 if the region is not a button."""
        x, y, w, h = roi
        region = frame[y : y + h, x : x + w]
        if region.size == 0:
            return 0.0

        blue = region[:, :, 0].astype(np.int16)
        green = region[:, :, 1].astype(np.int16)
        red = region[:, :, 2].astype(np.int16)
        mask = (red > 100) & (red > green + 20) & (red > blue + 30)
        ratio = float(mask.mean())
        return ratio if ratio >= 0.35 else 0.0

    def _find_red_buttons(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> list[tuple[int, int, int, int]]:
        """Locate large red button rectangles inside the action area."""
        import cv2

        x, y, w, h = roi
        region = frame[y : y + h, x : x + w]
        if region.size == 0:
            return []

        blue = region[:, :, 0].astype(np.int16)
        green = region[:, :, 1].astype(np.int16)
        red = region[:, :, 2].astype(np.int16)
        mask = ((red > 100) & (red > green + 20) & (red > blue + 30)).astype(np.uint8) * 255
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        buttons = []
        for contour in contours:
            bx, by, bw, bh = cv2.boundingRect(contour)
            area = bw * bh
            if area < 2500 or bw < 80 or bh < 30:
                continue
            if by < h * 0.35:
                continue
            buttons.append((x + bx, y + by, bw, bh))

        return sorted(buttons, key=lambda item: item[0])

    def _count_checkbox_prompts(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> int:
        """Count dark pre-action checkbox controls in the action area."""
        import cv2

        x, y, w, h = roi
        region = frame[y : y + h, x : x + w]
        if region.size == 0:
            return 0

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for contour in contours:
            bx, by, bw, bh = cv2.boundingRect(contour)
            if 90 <= bw <= 190 and 18 <= bh <= 40 and by >= h * 0.2:
                boxes.append((bx, by, bw, bh))

        deduped = []
        for box in sorted(boxes, key=lambda item: (item[1], item[0])):
            if any(
                abs(box[0] - existing[0]) < 6 and abs(box[1] - existing[1]) < 6
                for existing in deduped
            ):
                continue
            deduped.append(box)

        return len(deduped)

    def _white_pixel_count(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        *,
        upper: bool,
    ) -> int:
        """Count bright text pixels in the upper or lower half of a button."""
        import cv2

        x, y, w, h = roi
        region = frame[y : y + h, x : x + w]
        if region.size == 0:
            return 0
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        split = int(h * 0.48)
        half = gray[:split, :] if upper else gray[split:, :]
        mask = cv2.inRange(half, 180, 255)
        return int(mask.sum() / 255)

    def _classify_call_or_check(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> str:
        """Distinguish Call from Check using two-line versus centered text."""
        upper_white = self._white_pixel_count(frame, roi, upper=True)
        return "call" if upper_white >= 100 else "check"

    def _classify_raise_or_bet(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> str:
        """Distinguish Raise To from Bet using the larger two-word label."""
        upper_white = self._white_pixel_count(frame, roi, upper=True)
        return "raise" if upper_white >= 280 else "bet"
