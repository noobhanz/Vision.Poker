"""Tests for OCR engine."""

import pytest
import numpy as np

from vision.ocr_engine import OCREngine


class TestOCRNumberCleaning:
    """Test number extraction and cleaning."""

    @pytest.fixture
    def engine(self):
        return OCREngine()

    def test_clean_currency_symbol(self, engine):
        """Clean dollar signs."""
        result = engine._clean_number("$100")
        assert result == 100.0

    def test_clean_thousands_separator(self, engine):
        """Handle comma separators."""
        result = engine._clean_number("1,234")
        assert result == 1234.0

    def test_clean_bb_suffix(self, engine):
        """Handle BB (big blinds) suffix."""
        result = engine._clean_number("50BB")
        assert result == 50.0

        result = engine._clean_number("25.5 bb")
        assert result == 25.5

    def test_clean_k_suffix(self, engine):
        """Handle K (thousands) suffix."""
        result = engine._clean_number("2.5K")
        assert result == 2500.0

    def test_clean_m_suffix(self, engine):
        """Handle M (millions) suffix."""
        result = engine._clean_number("1.2M")
        assert result == 1200000.0

    def test_clean_whitespace(self, engine):
        """Handle whitespace."""
        result = engine._clean_number("  100  ")
        assert result == 100.0

    def test_clean_empty_string(self, engine):
        """Handle empty string."""
        result = engine._clean_number("")
        assert result is None

    def test_clean_no_numbers(self, engine):
        """Handle string with no numbers."""
        result = engine._clean_number("abc")
        assert result is None

    def test_clean_decimal(self, engine):
        """Handle decimal values."""
        result = engine._clean_number("$45.50")
        assert result == 45.5

    def test_clean_false_currency_prefix(self, engine):
        """Handle dollar signs misread as a leading 8 in PokerStars OCR."""
        assert engine._clean_number("8006") == 0.06
        assert engine._clean_number("80.04") == 0.04
        assert engine._clean_number("81.98") == 1.98
        assert engine._clean_number("82.03") == 2.03

    def test_clean_compact_cents_without_breaking_whole_numbers(self, engine):
        """Parse compact cents while preserving ordinary whole numbers."""
        assert engine._clean_number("006") == 0.06
        assert engine._clean_number("100") == 100.0
        assert engine._clean_number("$100") == 100.0


class TestOCRRegionExtraction:
    """Test OCR region reading (requires EasyOCR to be installed)."""

    @pytest.fixture
    def engine(self):
        return OCREngine()

    def test_invalid_roi_returns_none(self, engine):
        """Invalid ROI should return None."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.read_number(frame, (-10, -10, 50, 50))
        assert result is None

    def test_roi_out_of_bounds(self, engine):
        """ROI outside frame should return None."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.read_number(frame, (90, 90, 50, 50))
        assert result is None

    def test_empty_region_returns_none(self, engine):
        """Empty region should return None."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.read_number(frame, (10, 10, 0, 0))
        assert result is None
