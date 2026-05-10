"""
Extract numeric text from defined ROI regions.
Regions: pot size, bet to call, hero stack, villain stacks.
Cleans extracted text: strip '$', ',', 'BB' suffixes.
Returns float or None if extraction fails.
"""

import re
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

    def __init__(self, use_gpu: bool = False):
        """
        Initialize OCR engine.

        Args:
            use_gpu: Whether to use GPU for OCR (requires CUDA)
        """
        self.use_gpu = use_gpu
        self._reader = None

    @property
    def reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            try:
                import easyocr

                self._reader = easyocr.Reader(["en"], gpu=self.use_gpu, verbose=False)
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

        # Extract the numeric portion
        num_match = re.search(r"[\d.]+", text)
        if num_match:
            try:
                return float(num_match.group())
            except ValueError:
                pass

        return None

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

        try:
            # Run OCR
            results = self.reader.readtext(region)

            if not results:
                return None

            # Combine all detected text
            all_text = " ".join([r[1] for r in results])

            return self._clean_number(all_text)

        except Exception:
            return None

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
