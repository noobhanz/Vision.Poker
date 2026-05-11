"""
Detect playing cards in a frame using YOLOv8.
Falls back to template matching if model confidence < threshold.
Returns list of detected Card objects with bounding boxes.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# Card labels: 52 cards using rank + suit format
RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades
ALL_CARDS = [r + s for r in RANKS for s in SUITS]


@dataclass
class DetectedCard:
    """A detected card with bounding box and confidence."""

    card: str  # e.g., "Ah" for Ace of hearts
    confidence: float
    bbox: tuple[int, int, int, int]  # (x, y, width, height)

    @property
    def rank(self) -> str:
        """Get the card rank."""
        return self.card[0]

    @property
    def suit(self) -> str:
        """Get the card suit."""
        return self.card[1]


class CardDetector:
    """
    Detect playing cards using YOLOv8 with template matching fallback.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.75,
        template_dir: Optional[Path] = None,
    ):
        """
        Initialize card detector.

        Args:
            model_path: Path to fine-tuned YOLOv8 model (.pt file)
            confidence_threshold: Minimum confidence for YOLO detections
            template_dir: Directory containing template images for fallback
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.template_dir = template_dir or Path(__file__).parent / "templates"

        self._model = None
        self._templates: dict[str, list[np.ndarray]] = {}
        self._rank_templates: dict[str, np.ndarray] = {}
        self._suit_templates: dict[str, np.ndarray] = {}

    @property
    def model(self):
        """Lazy-load the YOLO model."""
        if self._model is None and self.model_path:
            try:
                from ultralytics import YOLO

                self._model = YOLO(self.model_path)
            except ImportError:
                print("ultralytics not installed. Run: pip install ultralytics")
            except Exception as e:
                print(f"Failed to load YOLO model: {e}")
        return self._model

    def _load_templates(self) -> None:
        """Load template images for fallback detection."""
        if self._templates:
            return

        import cv2

        if not self.template_dir.exists():
            return

        for card in ALL_CARDS:
            template_path = self.template_dir / f"{card}.png"
            if template_path.exists():
                template = cv2.imread(str(template_path))
                if template is not None:
                    self._templates.setdefault(card, []).append(template)

            variant_dir = self.template_dir / "cards"
            if variant_dir.exists():
                for variant_path in sorted(variant_dir.glob(f"{card}_*.png")):
                    template = cv2.imread(str(variant_path))
                    if template is not None:
                        self._templates.setdefault(card, []).append(template)

    def _load_rank_suit_templates(self) -> None:
        """Load fixed-slot rank and suit templates for lightweight classification."""
        if self._rank_templates and self._suit_templates:
            return

        import cv2

        rank_dir = self.template_dir / "ranks"
        suit_dir = self.template_dir / "suits"

        if rank_dir.exists():
            for rank in RANKS:
                template_path = rank_dir / f"{rank}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self._rank_templates[rank] = self._preprocess_for_template(template)

        if suit_dir.exists():
            for suit in SUITS:
                template_path = suit_dir / f"{suit}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self._suit_templates[suit] = self._preprocess_for_template(template)

    def _preprocess_for_template(self, image: np.ndarray) -> np.ndarray:
        """Normalize a crop before template matching."""
        import cv2

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.equalizeHist(gray)

        # Preserve rank/suit shapes while reducing background variation.
        _, thresholded = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY | cv2.THRESH_OTSU,
        )
        return thresholded

    def _best_template_match(
        self,
        image: np.ndarray,
        templates: dict[str, np.ndarray],
    ) -> tuple[Optional[str], float]:
        """Return the best template label and confidence for an image crop."""
        import cv2

        best_label: Optional[str] = None
        best_score = 0.0

        for label, template in templates.items():
            if image.size == 0:
                continue

            search_template = template
            if (
                template.shape[0] > image.shape[0]
                or template.shape[1] > image.shape[1]
            ):
                search_template = cv2.resize(
                    template,
                    (image.shape[1], image.shape[0]),
                    interpolation=cv2.INTER_AREA,
                )

            result = cv2.matchTemplate(image, search_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_label = label
                best_score = float(max_val)

        return best_label, best_score

    def _classify_rank_suit_from_crop(
        self,
        crop: np.ndarray,
        threshold: float,
    ) -> Optional[DetectedCard]:
        """Classify a card crop that is already isolated to one card slot."""
        if crop.size == 0:
            return None

        h, w = crop.shape[:2]

        # PokerStars prints the rank and suit vertically in the top-left card corner.
        rank_region = crop[
            int(h * 0.04) : int(h * 0.30),
            int(w * 0.04) : int(w * 0.38),
        ]
        suit_region = crop[
            int(h * 0.24) : int(h * 0.52),
            int(w * 0.04) : int(w * 0.38),
        ]

        rank_prepared = self._preprocess_for_template(rank_region)
        suit_prepared = self._preprocess_for_template(suit_region)

        rank, rank_score = self._best_template_match(
            rank_prepared,
            self._rank_templates,
        )
        suit, suit_score = self._best_template_match(
            suit_prepared,
            self._suit_templates,
        )

        confidence = min(rank_score, suit_score)
        if rank is None or suit is None or confidence < threshold:
            return None

        return DetectedCard(
            card=f"{rank}{suit}",
            confidence=confidence,
            bbox=(0, 0, w, h),
        )

    def detect_rank_suit_template(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        threshold: float = 0.72,
    ) -> list[DetectedCard]:
        """
        Classify a known card slot using separate rank and suit templates.

        This is the lightweight MVP path for fixed ROIs: the caller already knows
        where the card should be, so we only classify the top-left card corner.
        """
        self._load_rank_suit_templates()

        if not self._rank_templates or not self._suit_templates:
            return []

        x, y, w, h = roi
        crop = frame[y : y + h, x : x + w]
        detected = self._classify_rank_suit_from_crop(crop, threshold)
        if detected is None:
            return []

        return [detected]

    def detect_yolo(
        self,
        frame: np.ndarray,
        roi: Optional[tuple[int, int, int, int]] = None,
    ) -> list[DetectedCard]:
        """
        Detect cards using YOLOv8.

        Args:
            frame: Full frame or ROI as np.ndarray (BGR)
            roi: Optional (x, y, w, h) to crop before detection

        Returns:
            List of DetectedCard objects
        """
        if self.model is None:
            return []

        # Crop to ROI if specified
        if roi:
            x, y, w, h = roi
            frame = frame[y : y + h, x : x + w]

        try:
            results = self.model(frame, verbose=False)

            detected = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for i, box in enumerate(boxes):
                    conf = float(box.conf[0])
                    if conf < self.confidence_threshold:
                        continue

                    cls_id = int(box.cls[0])
                    if cls_id < len(ALL_CARDS):
                        card_name = ALL_CARDS[cls_id]
                    else:
                        continue

                    # Get bounding box
                    xyxy = box.xyxy[0].cpu().numpy()
                    bbox = (
                        int(xyxy[0]),
                        int(xyxy[1]),
                        int(xyxy[2] - xyxy[0]),
                        int(xyxy[3] - xyxy[1]),
                    )

                    detected.append(
                        DetectedCard(card=card_name, confidence=conf, bbox=bbox)
                    )

            return detected

        except Exception as e:
            print(f"YOLO detection error: {e}")
            return []

    def detect_template(
        self,
        frame: np.ndarray,
        roi: Optional[tuple[int, int, int, int]] = None,
        threshold: float = 0.8,
    ) -> list[DetectedCard]:
        """
        Detect cards using template matching fallback.

        Args:
            frame: Full frame as np.ndarray (BGR)
            roi: Optional (x, y, w, h) to crop before detection
            threshold: Template matching threshold (0.0-1.0)

        Returns:
            List of DetectedCard objects
        """
        import cv2

        self._load_templates()

        if not self._templates:
            if roi is None:
                return []
            return self.detect_rank_suit_template(frame, roi, threshold=threshold)

        # Crop to ROI if specified
        if roi:
            x, y, w, h = roi
            frame = frame[y : y + h, x : x + w]

        detected = []

        for card_name, templates in self._templates.items():
            for template in templates:
                # Resize if the slot is a pixel or two smaller than the template source.
                if (
                    template.shape[0] > frame.shape[0]
                    or template.shape[1] > frame.shape[1]
                ):
                    template = cv2.resize(
                        template,
                        (frame.shape[1], frame.shape[0]),
                        interpolation=cv2.INTER_AREA,
                    )

                # Template matching
                result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= threshold)

                for pt in zip(*locations[::-1]):
                    # Check for overlapping detections
                    overlap = False
                    for det in detected:
                        if det.card == card_name:
                            # Simple overlap check
                            if (
                                abs(pt[0] - det.bbox[0]) < template.shape[1] // 2
                                and abs(pt[1] - det.bbox[1]) < template.shape[0] // 2
                            ):
                                overlap = True
                                break

                    if not overlap:
                        detected.append(
                            DetectedCard(
                                card=card_name,
                                confidence=float(result[pt[1], pt[0]]),
                                bbox=(pt[0], pt[1], template.shape[1], template.shape[0]),
                            )
                        )

        if roi and not detected:
            detected.extend(
                self.detect_rank_suit_template(
                    frame,
                    (0, 0, frame.shape[1], frame.shape[0]),
                    threshold=min(threshold, 0.72),
                )
            )

        return detected

    def detect(
        self,
        frame: np.ndarray,
        roi: Optional[tuple[int, int, int, int]] = None,
    ) -> list[DetectedCard]:
        """
        Detect cards, using YOLO with template fallback.

        Args:
            frame: Full frame as np.ndarray (BGR)
            roi: Optional (x, y, w, h) to search within

        Returns:
            List of DetectedCard objects
        """
        # Try YOLO first
        detected = self.detect_yolo(frame, roi)

        # If YOLO found cards with good confidence, return them
        if detected and all(d.confidence >= self.confidence_threshold for d in detected):
            return detected

        # Fall back to template matching
        template_detected = self.detect_template(frame, roi)

        # Merge results, preferring YOLO if available
        if not detected:
            return template_detected

        # If YOLO had some detections, supplement with templates for missing cards
        yolo_cards = {d.card for d in detected}
        for td in template_detected:
            if td.card not in yolo_cards:
                detected.append(td)

        return detected

    def detect_single_card(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> Optional[DetectedCard]:
        """
        Detect a single card in a specific ROI.
        Returns the highest confidence detection.

        Args:
            frame: Full frame as np.ndarray (BGR)
            roi: Region (x, y, w, h) expected to contain one card

        Returns:
            DetectedCard or None if no card found
        """
        detected = self.detect(frame, roi)

        if not detected:
            return None

        # Return highest confidence detection
        return max(detected, key=lambda d: d.confidence)
