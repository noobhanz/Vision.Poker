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


@dataclass
class NormalizedCardSlot:
    """A fixed card slot cropped down to the visible card surface."""

    crop: np.ndarray
    bbox: tuple[int, int, int, int]
    status: str


class CardDetector:
    """
    Detect playing cards using YOLOv8 with template matching fallback.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.75,
        template_dir: Optional[Path] = None,
        min_card_white_ratio: float = 0.12,
        min_full_card_margin: float = 0.01,
        full_card_ambiguity_band: float = 0.03,
    ):
        """
        Initialize card detector.

        Args:
            model_path: Path to fine-tuned YOLOv8 model (.pt file)
            confidence_threshold: Minimum confidence for YOLO detections
            template_dir: Directory containing template images for fallback
            min_card_white_ratio: Minimum bright-pixel ratio expected in a fixed card slot
            min_full_card_margin: Required gap for near-threshold full-card matches
            full_card_ambiguity_band: Score range above threshold treated as near-threshold
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.min_card_white_ratio = min_card_white_ratio
        self.min_full_card_margin = min_full_card_margin
        self.full_card_ambiguity_band = full_card_ambiguity_band
        self.template_dir = template_dir or Path(__file__).parent / "templates"

        self._model = None
        self._model_load_attempted = False
        self._templates: dict[str, list[np.ndarray]] = {}
        self._rank_templates: dict[str, list[np.ndarray]] = {}
        self._suit_templates: dict[str, list[np.ndarray]] = {}

    @property
    def model(self):
        """Lazy-load the YOLO model."""
        if self._model is None and self.model_path and not self._model_load_attempted:
            self._model_load_attempted = True
            if not Path(self.model_path).exists():
                return None

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
                        self._rank_templates.setdefault(rank, []).append(
                            self._preprocess_for_template(template)
                        )

        if suit_dir.exists():
            for suit in SUITS:
                template_path = suit_dir / f"{suit}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self._suit_templates.setdefault(suit, []).append(
                            self._preprocess_for_template(template)
                        )

        # Full-card variants are still useful as training material for the
        # scalable rank/suit path. Deriving corner glyph templates from them
        # gives us multiple sizes and slight rendering variants without making
        # production depend on exact 52-card full-template coverage.
        self._load_templates()
        for card, templates in self._templates.items():
            if len(card) != 2:
                continue
            rank, suit = card[0].upper(), card[1].lower()
            if rank not in RANKS or suit not in SUITS:
                continue
            for template in templates:
                if float(template.std()) < 2.0:
                    continue
                normalized = self._normalize_card_crop(template).crop
                rank_region, suit_region = self._rank_suit_regions(normalized)
                if rank_region.size and float(rank_region.std()) >= 2.0:
                    prepared_rank = self._preprocess_for_template(rank_region)
                    if float(prepared_rank.std()) >= 2.0:
                        self._rank_templates.setdefault(rank, []).append(prepared_rank)
                if suit_region.size and float(suit_region.std()) >= 2.0:
                    prepared_suit = self._preprocess_for_template(suit_region)
                    if float(prepared_suit.std()) >= 2.0:
                        self._suit_templates.setdefault(suit, []).append(prepared_suit)

    def _preprocess_for_template(self, image: np.ndarray) -> np.ndarray:
        """Normalize a rank/suit glyph crop before template matching."""
        import cv2

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        if gray.size == 0:
            return gray

        # Raw card crops are mostly white with dark/red glyphs. Existing test
        # templates are often white glyphs on black. Infer polarity and always
        # normalize to white foreground on black background.
        foreground = gray > 128 if float(gray.mean()) < 128 else gray < 185
        coords = np.argwhere(foreground)
        if coords.size == 0:
            return np.zeros((32, 28), dtype=np.uint8)

        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        pad = 0
        y0 = max(0, int(y0) - pad)
        x0 = max(0, int(x0) - pad)
        y1 = min(gray.shape[0], int(y1) + pad)
        x1 = min(gray.shape[1], int(x1) + pad)
        glyph = foreground[y0:y1, x0:x1].astype(np.uint8) * 255

        h, w = glyph.shape[:2]
        target_w, target_h = 28, 32
        scale = min(target_w / max(1, w), target_h / max(1, h))
        resized_w = max(1, int(round(w * scale)))
        resized_h = max(1, int(round(h * scale)))
        glyph = cv2.resize(
            glyph,
            (resized_w, resized_h),
            interpolation=cv2.INTER_NEAREST,
        )

        canvas = np.zeros((target_h, target_w), dtype=np.uint8)
        x_off = (target_w - resized_w) // 2
        y_off = (target_h - resized_h) // 2
        canvas[y_off : y_off + resized_h, x_off : x_off + resized_w] = glyph
        return canvas

    def _has_card_like_pixels(self, crop: np.ndarray) -> bool:
        """Return whether a fixed slot contains enough bright card surface."""
        import cv2

        if crop.size == 0:
            return False

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        return float((gray > 180).mean()) >= self.min_card_white_ratio

    def has_card_like_pixels(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> bool:
        """Return whether a frame ROI looks occupied by a card."""
        x, y, w, h = roi
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return False
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            return False
        return self._has_card_like_pixels(frame[y : y + h, x : x + w])

    def _best_template_match(
        self,
        image: np.ndarray,
        templates: dict[str, list[np.ndarray]],
    ) -> tuple[Optional[str], float]:
        """Return the best template label and confidence for an image crop."""
        import cv2

        best_label: Optional[str] = None
        best_score = 0.0

        if image.size == 0:
            return best_label, best_score

        for label, label_templates in templates.items():
            for template in label_templates:
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
                score = max(float(max_val), self._binary_glyph_similarity(image, search_template))

                if score > best_score:
                    best_label = label
                    best_score = score

        return best_label, best_score

    def _binary_glyph_similarity(self, image: np.ndarray, template: np.ndarray) -> float:
        """Return a Dice-style similarity for normalized binary glyph masks."""
        if image.shape != template.shape or image.size == 0:
            return 0.0
        image_mask = image > 127
        template_mask = template > 127
        denom = int(image_mask.sum()) + int(template_mask.sum())
        if denom == 0:
            return 0.0
        overlap = int(np.logical_and(image_mask, template_mask).sum())
        return (2.0 * overlap) / denom

    def _rank_suit_regions(self, crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return the rank and suit subregions from an isolated card crop."""
        h, w = crop.shape[:2]
        rank_region = crop[
            int(h * 0.04) : int(h * 0.30),
            int(w * 0.04) : int(w * 0.38),
        ]
        suit_region = crop[
            int(h * 0.24) : int(h * 0.52),
            int(w * 0.04) : int(w * 0.38),
        ]
        return rank_region, suit_region

    def _normalize_card_crop(self, crop: np.ndarray) -> NormalizedCardSlot:
        """
        Find the visible card surface inside a fixed slot crop.

        Fixed ROIs are only an approximate slot. In live capture, the window can
        resize, the table can shift by a few pixels, and hero cards may be partly
        covered by the player badge. We normalize by locating the bright card
        rectangle and cropping to it before rank/suit reading.
        """
        import cv2

        if crop.size == 0:
            return NormalizedCardSlot(crop=crop, bbox=(0, 0, 0, 0), status="EMPTY_CROP")

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Close small rank/suit/pip holes so the card face becomes one surface.
        k = max(3, int(round(min(crop.shape[:2]) * 0.08)))
        kernel = np.ones((k, k), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_box: tuple[int, int, int, int] | None = None
        best_score = -1.0
        crop_h, crop_w = crop.shape[:2]

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < max(8, crop_w * 0.25) or h < max(12, crop_h * 0.25):
                continue

            area_ratio = (w * h) / float(crop_w * crop_h)
            aspect = w / float(h)
            # Fully visible cards are tall, but hero cards are often partly
            # covered by the seat badge. A top-only card face is wide; keep it
            # because its rank/suit corner is still the useful signal.
            if not 0.35 <= aspect <= 3.2:
                continue

            # Prefer large card-like regions near the top-left of the slot.
            top_left_penalty = (x / max(1, crop_w)) + (y / max(1, crop_h))
            score = area_ratio - 0.12 * top_left_penalty
            if score > best_score:
                best_box = (x, y, w, h)
                best_score = score

        if best_box is None:
            return NormalizedCardSlot(
                crop=crop,
                bbox=(0, 0, crop_w, crop_h),
                status="RAW_SLOT",
            )

        x, y, w, h = best_box
        pad = max(1, int(round(min(w, h) * 0.03)))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(crop_w, x + w + pad)
        y1 = min(crop_h, y + h + pad)
        normalized = crop[y0:y1, x0:x1]

        if normalized.size == 0:
            return NormalizedCardSlot(
                crop=crop,
                bbox=(0, 0, crop_w, crop_h),
                status="RAW_SLOT",
            )

        return NormalizedCardSlot(
            crop=normalized,
            bbox=(x0, y0, x1 - x0, y1 - y0),
            status="NORMALIZED",
        )

    def _template_scores(
        self,
        image: np.ndarray,
        templates: dict[str, list[np.ndarray]],
    ) -> list[tuple[str, float]]:
        """Return template scores sorted best-first for diagnostic output."""
        import cv2

        scores: list[tuple[str, float]] = []
        if image.size == 0:
            return scores

        for label, label_templates in templates.items():
            best = 0.0
            for template in label_templates:
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
                score = max(
                    float(max_val),
                    self._binary_glyph_similarity(image, search_template),
                )
                best = max(best, score)
            scores.append((label, best))

        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _prepare_fixed_slot_match(
        self,
        image: np.ndarray,
        template: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Normalize a fixed-slot crop and template to compatible dimensions.

        ROI scaling tells us where the card slot is, not the exact pixel size the
        template was extracted at. For fixed slots, the crop should be compared
        as the same card rendered at a different scale, so resize the larger side
        to the smaller side before template scoring.
        """
        import cv2

        prepared_image = image
        prepared_template = template

        if image.shape[:2] == template.shape[:2]:
            return prepared_image, prepared_template

        if image.shape[0] >= template.shape[0] and image.shape[1] >= template.shape[1]:
            prepared_image = cv2.resize(
                image,
                (template.shape[1], template.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
        elif template.shape[0] >= image.shape[0] and template.shape[1] >= image.shape[1]:
            prepared_template = cv2.resize(
                template,
                (image.shape[1], image.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

        if (
            prepared_template.shape[0] > prepared_image.shape[0]
            or prepared_template.shape[1] > prepared_image.shape[1]
        ):
            prepared_template = cv2.resize(
                prepared_template,
                (prepared_image.shape[1], prepared_image.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

        return prepared_image, prepared_template

    def _bright_content_crop(self, image: np.ndarray) -> np.ndarray:
        """Return the bright card surface inside a fixed slot crop."""
        import cv2

        if image.size == 0:
            return image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        mask = gray > 160
        coords = np.argwhere(mask)
        if coords.size == 0:
            return image

        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        pad = 2
        y0 = max(0, int(y0) - pad)
        x0 = max(0, int(x0) - pad)
        y1 = min(image.shape[0], int(y1) + pad)
        x1 = min(image.shape[1], int(x1) + pad)

        # Avoid turning a mostly full ROI into an almost identical copy while
        # still clipping table labels or empty slot space below the card.
        if y1 <= y0 or x1 <= x0:
            return image
        return image[y0:y1, x0:x1]

    def _template_max_score(self, image: np.ndarray, template: np.ndarray) -> float:
        """Return the best match score for one template against one image."""
        import cv2

        if image.size == 0:
            return 0.0
        if float(template.std()) < 1.0:
            return 0.0

        search_template = template
        if template.shape[0] > image.shape[0] or template.shape[1] > image.shape[1]:
            search_template = cv2.resize(
                template,
                (image.shape[1], image.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

        result = cv2.matchTemplate(image, search_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        sliding_score = float(max_val)

        fixed_score = 0.0
        if image.shape[:2] != template.shape[:2]:
            image_content = self._bright_content_crop(image)
            template_content = self._bright_content_crop(template)
            prepared_image, prepared_template = self._prepare_fixed_slot_match(
                image_content,
                template_content,
            )
            fixed_result = cv2.matchTemplate(
                prepared_image,
                prepared_template,
                cv2.TM_CCOEFF_NORMED,
            )
            _, fixed_val, _, _ = cv2.minMaxLoc(fixed_result)
            fixed_score = float(fixed_val)

        return max(sliding_score, fixed_score)

    def _full_card_scores(self, crop: np.ndarray) -> list[tuple[str, float]]:
        """Return best full-card template scores sorted best-first."""
        scores: list[tuple[str, float]] = []
        for card, templates in self._templates.items():
            if not templates:
                continue
            best = max(self._template_max_score(crop, template) for template in templates)
            scores.append((card, best))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _full_card_match_status(
        self,
        scores: list[tuple[str, float]],
        threshold: float,
    ) -> tuple[bool, str]:
        """Decide whether a fixed-slot full-card match is confident enough."""
        if not scores:
            return False, "NO_MATCHES"

        confidence = scores[0][1]
        if confidence < threshold:
            return False, "LOW_CONFIDENCE"

        if (
            len(scores) >= 2
            and confidence - scores[1][1] < self.min_full_card_margin
        ):
            return False, "AMBIGUOUS_MATCH"

        near_threshold = confidence < threshold + self.full_card_ambiguity_band
        if (
            near_threshold
            and len(scores) >= 2
            and confidence - scores[1][1] < self.min_full_card_margin
        ):
            return False, "AMBIGUOUS_MATCH"

        return True, "ACCEPTED"

    def _classify_rank_suit_from_crop(
        self,
        crop: np.ndarray,
        threshold: float,
    ) -> Optional[DetectedCard]:
        """Classify a card crop that is already isolated to one card slot."""
        if crop.size == 0:
            return None

        h, w = crop.shape[:2]
        rank_region, suit_region = self._rank_suit_regions(crop)

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
        if not self._has_card_like_pixels(crop):
            return []

        normalized = self._normalize_card_crop(crop)
        detected = self._classify_rank_suit_from_crop(normalized.crop, threshold)
        if detected is None:
            return []

        detected.bbox = normalized.bbox
        return [detected]

    def rank_suit_diagnostics(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        threshold: float = 0.72,
        top_n: int = 5,
    ) -> dict:
        """
        Explain fixed-slot rank/suit classification for one card ROI.

        The returned dict is intentionally JSON-friendly so diagnostic tools can
        store exactly what the recognizer saw, which labels competed, and why a
        slot was accepted or rejected.
        """
        self._load_rank_suit_templates()

        x, y, w, h = roi
        result = {
            "roi": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
            "threshold": threshold,
            "top_n": top_n,
            "accepted": False,
            "accepted_card": None,
            "confidence": 0.0,
            "rank_candidates": [],
            "suit_candidates": [],
            "rank_margin": None,
            "suit_margin": None,
            "normalization": None,
            "status": "NO_TEMPLATES",
        }

        if not self._rank_templates or not self._suit_templates:
            return result

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            result["status"] = "INVALID_ROI"
            return result
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            result["status"] = "ROI_OUT_OF_BOUNDS"
            return result

        crop = frame[y : y + h, x : x + w]
        if crop.size == 0:
            result["status"] = "EMPTY_CROP"
            return result

        if not self._has_card_like_pixels(crop):
            result["status"] = "EMPTY_SLOT"
            return result

        normalized = self._normalize_card_crop(crop)
        result["normalization"] = {
            "status": normalized.status,
            "bbox": {
                "x": int(normalized.bbox[0]),
                "y": int(normalized.bbox[1]),
                "w": int(normalized.bbox[2]),
                "h": int(normalized.bbox[3]),
            },
        }

        rank_region, suit_region = self._rank_suit_regions(normalized.crop)
        rank_prepared = self._preprocess_for_template(rank_region)
        suit_prepared = self._preprocess_for_template(suit_region)

        rank_scores = self._template_scores(rank_prepared, self._rank_templates)
        suit_scores = self._template_scores(suit_prepared, self._suit_templates)
        result["rank_candidates"] = [
            {"label": label, "score": round(score, 4)}
            for label, score in rank_scores[:top_n]
        ]
        result["suit_candidates"] = [
            {"label": label, "score": round(score, 4)}
            for label, score in suit_scores[:top_n]
        ]

        if len(rank_scores) >= 2:
            result["rank_margin"] = round(rank_scores[0][1] - rank_scores[1][1], 4)
        if len(suit_scores) >= 2:
            result["suit_margin"] = round(suit_scores[0][1] - suit_scores[1][1], 4)

        if not rank_scores or not suit_scores:
            result["status"] = "NO_MATCHES"
            return result

        rank, rank_score = rank_scores[0]
        suit, suit_score = suit_scores[0]
        confidence = min(rank_score, suit_score)
        result["accepted_card"] = f"{rank}{suit}"
        result["confidence"] = round(confidence, 4)
        result["accepted"] = confidence >= threshold
        result["status"] = "ACCEPTED" if confidence >= threshold else "LOW_CONFIDENCE"
        return result

    def full_card_template_diagnostics(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        threshold: float = 0.8,
        top_n: int = 5,
    ) -> dict:
        """
        Explain full-card template matching for one ROI.

        This complements rank/suit diagnostics because the production fallback
        can succeed through full-card variants before rank/suit matching runs.
        """
        self._load_templates()

        x, y, w, h = roi
        result = {
            "roi": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
            "threshold": threshold,
            "top_n": top_n,
            "accepted": False,
            "accepted_card": None,
            "confidence": 0.0,
            "card_candidates": [],
            "score_margin": None,
            "status": "NO_TEMPLATES",
        }

        if not self._templates:
            return result

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            result["status"] = "INVALID_ROI"
            return result
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            result["status"] = "ROI_OUT_OF_BOUNDS"
            return result

        crop = frame[y : y + h, x : x + w]
        if crop.size == 0:
            result["status"] = "EMPTY_CROP"
            return result

        if not self._has_card_like_pixels(crop):
            result["status"] = "EMPTY_SLOT"
            return result

        scores = self._full_card_scores(crop)
        result["card_candidates"] = [
            {"label": label, "score": round(score, 4)}
            for label, score in scores[:top_n]
        ]

        if len(scores) >= 2:
            result["score_margin"] = round(scores[0][1] - scores[1][1], 4)
        if not scores:
            result["status"] = "NO_MATCHES"
            return result

        card, confidence = scores[0]
        accepted, status = self._full_card_match_status(scores, threshold)
        result["accepted_card"] = card
        result["confidence"] = round(confidence, 4)
        result["accepted"] = accepted
        result["status"] = status
        return result

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
            if not self._has_card_like_pixels(frame):
                return []

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

        if roi:
            x, y, w, h = roi
            fixed_slot_threshold = min(threshold, 0.72)
            diagnostic = self.full_card_template_diagnostics(
                frame,
                roi,
                threshold=fixed_slot_threshold,
                top_n=2,
            )
            if diagnostic["accepted"]:
                return [
                    DetectedCard(
                        card=diagnostic["accepted_card"],
                        confidence=float(diagnostic["confidence"]),
                        bbox=(0, 0, w, h),
                    )
                ]

            if diagnostic["status"] in {
                "EMPTY_SLOT",
                "INVALID_ROI",
                "ROI_OUT_OF_BOUNDS",
                "EMPTY_CROP",
            }:
                return []

            # Rank/suit recognition is the scalable target path, but today it is
            # safest as the fallback when full-card evidence is absent or weak.
            # Diagnostics expose both paths so we can gate the eventual switch.
            return self.detect_rank_suit_template(
                frame,
                roi,
                threshold=min(threshold, 0.70),
            )

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
                    threshold=min(threshold, 0.70),
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
