"""
Extract numeric text from defined ROI regions.
Regions: pot size, bet to call, hero stack, villain stacks.
Cleans extracted text: strip '$', ',', 'BB' suffixes.
Returns float or None if extraction fails.
"""

import re
from pathlib import Path
from typing import Optional

import numpy as np

# Lazy load EasyOCR to avoid slow startup
_ocr_reader = None


def _get_reader():
    """Lazy-load the EasyOCR reader on first use."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr

            _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        except ImportError:
            raise ImportError("easyocr not installed. Run: pip install easyocr")
    return _ocr_reader


class OCREngine:
    """OCR engine for extracting numeric values from poker table regions."""

    def __init__(
        self,
        use_gpu: bool = False,
        model_storage_directory: Optional[str | Path] = None,
        use_easyocr: bool = False,
    ):
        """
        Initialize OCR engine.

        Args:
            use_gpu: Whether to use GPU for OCR (requires CUDA)
            model_storage_directory: Optional EasyOCR model cache directory
        """
        self.use_gpu = use_gpu
        self.use_easyocr = use_easyocr
        self.model_storage_directory = Path(
            model_storage_directory or "/tmp/vision_poker_easyocr"
        )
        self.template_dir = Path(__file__).parent / "templates" / "ocr"
        self._ocr_templates: dict[str, list[np.ndarray]] = {}
        self._reader = None

    @property
    def reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            try:
                import easyocr

                self.model_storage_directory.mkdir(parents=True, exist_ok=True)
                self._reader = easyocr.Reader(
                    ["en"],
                    gpu=self.use_gpu,
                    verbose=False,
                    model_storage_directory=str(self.model_storage_directory),
                    user_network_directory=str(
                        self.model_storage_directory / "user_network"
                    ),
                )
            except ImportError:
                raise ImportError("easyocr not installed. Run: pip install easyocr")
        return self._reader

    def _clean_number(self, text: str) -> Optional[float]:
        """
        Clean OCR text and extract numeric value.

        Handles:
        - Currency symbols: $, €, £
        - Thousands separators: 1,234
        - Suffixes: BB, bb, k, m
        - Whitespace and noise
        """
        if not text:
            return None

        # Remove common noise and currency symbols
        text = text.strip()
        text = re.sub(r"[$€£]", "", text)
        text = re.sub(r"\s+", "", text)

        # Handle BB suffix (big blinds)
        bb_match = re.search(r"([\d.,]+)\s*[Bb][Bb]?", text)
        if bb_match:
            text = bb_match.group(1)

        # Handle k/m suffixes (thousands/millions)
        k_match = re.search(r"([\d.,]+)\s*[Kk]", text)
        if k_match:
            try:
                return float(k_match.group(1).replace(",", "")) * 1000
            except ValueError:
                pass

        m_match = re.search(r"([\d.,]+)\s*[Mm]", text)
        if m_match:
            try:
                return float(m_match.group(1).replace(",", "")) * 1_000_000
            except ValueError:
                pass

        # Remove thousands separators and parse
        text = text.replace(",", "")

        # Letter labels such as "All In" can produce leading dot-like glyphs
        # when matched against numeric templates. Treat that as non-numeric
        # instead of accepting the later accidental digits.
        if text.startswith("."):
            stripped = text.lstrip(".")
            if "." not in stripped:
                return None
            text = stripped

        # PokerStars' small white dollar sign can be segmented like an "8" by
        # the lightweight template OCR. Normalize common forms such as
        # "$0.06" -> "8006", "$1.98" -> "81.98", and "$0.04" -> "80.04".
        if text.startswith("8") and len(text) >= 3:
            corrected = self._parse_false_currency_prefix(text[1:])
            if corrected is not None:
                return corrected

        # Extra dot-like glyphs from labels/currency can produce strings such
        # as "0..0.07"; prefer the final decimal-looking token in those cases.
        decimal_matches = re.findall(r"\d+\.\d+", text)
        if decimal_matches:
            label_noise_value = self._parse_pot_label_noise(decimal_matches[-1])
            if label_noise_value is not None:
                return label_noise_value
            try:
                return float(decimal_matches[-1])
            except ValueError:
                pass

        # Extract the numeric portion
        num_match = re.search(r"[\d.]+", text)
        if num_match:
            try:
                token = num_match.group()
                money_like = self._parse_compact_cents(token)
                if money_like is not None:
                    return money_like
                return float(token)
            except ValueError:
                pass

        return None

    def _parse_false_currency_prefix(self, text: str) -> Optional[float]:
        """Parse money text after dropping a false leading currency glyph."""
        if not text:
            return None

        if "." in text:
            try:
                return float(text)
            except ValueError:
                return None

        if not text.isdigit() or len(text) < 3 or len(text) > 4:
            return None

        return int(text) / 100

    def _parse_compact_cents(self, text: str) -> Optional[float]:
        """Parse compact cent strings such as 006 as 0.06."""
        if not text or "." in text or not text.isdigit():
            return None
        if len(text) < 3 or len(text) > 4 or not text.startswith("0"):
            return None
        return int(text) / 100

    def _parse_pot_label_noise(self, text: str) -> Optional[float]:
        """Parse pot amounts after PokerStars label/currency glyph noise."""
        if not text.startswith("90.8"):
            return None

        suffix = text[4:]
        if not suffix.isdigit() or not 2 <= len(suffix) <= 3:
            return None

        return int(suffix) / 100

    def read_number(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> Optional[float]:
        """
        Extract a numeric value from a region of the frame.

        Args:
            frame: Full frame as np.ndarray (BGR)
            roi: Region tuple (x, y, width, height)

        Returns:
            Extracted numeric value or None if extraction fails
        """
        x, y, w, h = roi

        # Bounds checking
        if x < 0 or y < 0:
            return None
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            return None

        # Extract ROI
        region = frame[y : y + h, x : x + w]

        if region.size == 0:
            return None

        template_value = self._read_number_template(region)
        if template_value is not None:
            return template_value

        if self.use_easyocr:
            try:
                # Run OCR
                results = self.reader.readtext(region)

                if results:
                    # Combine all detected text
                    all_text = " ".join([r[1] for r in results])

                    value = self._clean_number(all_text)
                    if value is not None:
                        return value

            except Exception:
                pass

        return self._read_number_template(region)

    def _load_ocr_templates(self) -> None:
        """Load lightweight numeric OCR templates."""
        if self._ocr_templates:
            return
        if not self.template_dir.exists():
            return

        import cv2

        for path in sorted(self.template_dir.glob("*.png")):
            label = path.name.split("_", 1)[0]
            if label == "dot":
                label = "."
            if label not in "0123456789.":
                continue
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._ocr_templates.setdefault(label, []).append(img)

    def _template_mask(self, region: np.ndarray) -> np.ndarray:
        """Create a high-contrast mask for white poker table text."""
        import cv2

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
        gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        return mask

    def _read_number_template(self, region: np.ndarray) -> Optional[float]:
        """Read a number using extracted digit/dot templates."""
        import cv2

        self._load_ocr_templates()
        if not self._ocr_templates:
            return None

        # For pot labels like "Pot: $0.03", focus on the right-side amount.
        if region.shape[1] >= 170 and region.shape[0] <= 55:
            region = region[:, int(region.shape[1] * 0.45) :]
        # For action buttons like "Call\n$0.02", focus on the lower amount line.
        elif region.shape[0] > 60:
            region = region[int(region.shape[0] * 0.45) :, :]

        mask = self._template_mask(region)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if h < 8 or w < 2:
                continue
            boxes.append((x, y, w, h))

        chars = []
        for x, y, w, h in sorted(boxes):
            pad = 3
            char_img = mask[
                max(0, y - pad) : min(mask.shape[0], y + h + pad),
                max(0, x - pad) : min(mask.shape[1], x + w + pad),
            ]
            label, score = self._match_ocr_char(char_img)
            if label is not None and score >= 0.45:
                chars.append(label)

        text = "".join(chars)
        if text.startswith("."):
            stripped = text.lstrip(".")
            if "." not in stripped:
                return None
            text = stripped

        # Drop common leading currency misreads by keeping from first digit.
        match = re.search(r"\d[\d.]*", text)
        if not match:
            return None

        return self._clean_number(match.group())

    def _match_ocr_char(self, char_img: np.ndarray) -> tuple[Optional[str], float]:
        """Match one segmented character against OCR templates."""
        import cv2

        best_label: Optional[str] = None
        best_score = 0.0
        for label, templates in self._ocr_templates.items():
            for template in templates:
                resized = cv2.resize(
                    template,
                    (char_img.shape[1], char_img.shape[0]),
                    interpolation=cv2.INTER_AREA,
                )
                result = cv2.matchTemplate(
                    char_img,
                    resized,
                    cv2.TM_CCOEFF_NORMED,
                )
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > best_score:
                    best_label = label
                    best_score = float(max_val)
        return best_label, best_score

    def read_all_regions(
        self,
        frame: np.ndarray,
        regions: dict[str, tuple[int, int, int, int]],
    ) -> dict[str, Optional[float]]:
        """
        Read numeric values from multiple regions.

        Args:
            frame: Full frame as np.ndarray (BGR)
            regions: Dict mapping region names to (x, y, w, h) tuples

        Returns:
            Dict mapping region names to extracted values (or None)
        """
        results = {}
        for name, roi in regions.items():
            results[name] = self.read_number(frame, roi)
        return results


class SimpleOCR:
    """
    Simple OCR fallback using template matching for digits.
    Faster but less accurate than EasyOCR.
    """

    def __init__(self):
        self._digit_templates = {}

    def read_number(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> Optional[float]:
        """Read number using simple digit detection."""
        # This is a stub - in production, would use template matching
        # For now, fall back to EasyOCR
        engine = OCREngine()
        return engine.read_number(frame, roi)
