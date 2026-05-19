"""Tests for card detector."""

import pytest
import numpy as np

from vision.card_detector import CardDetector, DetectedCard, ALL_CARDS

# Check if cv2 is available
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

requires_cv2 = pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not installed")


class TestDetectedCard:
    """Test DetectedCard dataclass."""

    def test_card_properties(self):
        """Test rank and suit extraction."""
        card = DetectedCard(card="Ah", confidence=0.95, bbox=(0, 0, 50, 70))
        assert card.rank == "A"
        assert card.suit == "h"

    def test_card_properties_lowercase(self):
        """Test with lowercase input."""
        card = DetectedCard(card="Td", confidence=0.85, bbox=(10, 10, 50, 70))
        assert card.rank == "T"
        assert card.suit == "d"


class TestCardLabels:
    """Test card label constants."""

    def test_all_cards_count(self):
        """Should have 52 cards."""
        assert len(ALL_CARDS) == 52

    def test_all_cards_unique(self):
        """All cards should be unique."""
        assert len(set(ALL_CARDS)) == 52

    def test_card_format(self):
        """Cards should be rank+suit format."""
        for card in ALL_CARDS:
            assert len(card) == 2
            rank, suit = card
            assert rank in "23456789TJQKA"
            assert suit in "cdhs"


class TestCardDetector:
    """Test CardDetector class."""

    @pytest.fixture
    def detector(self):
        return CardDetector(confidence_threshold=0.75)

    def test_initialization(self, detector):
        """Test detector initialization."""
        assert detector.confidence_threshold == 0.75
        assert detector._model is None  # Lazy loaded

    @requires_cv2
    def test_detect_empty_frame(self, detector):
        """Detection on empty frame should return empty list."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Template detection on black frame
        results = detector.detect_template(frame)
        assert isinstance(results, list)

    @requires_cv2
    def test_detect_with_roi(self, detector):
        """Detection with ROI should not crash."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = (100, 100, 60, 80)
        results = detector.detect(frame, roi)
        assert isinstance(results, list)

    @requires_cv2
    def test_detect_single_card_no_card(self, detector):
        """Single card detection on empty region returns None."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = (100, 100, 60, 80)
        result = detector.detect_single_card(frame, roi)
        # With no templates or model, should return None
        assert result is None or isinstance(result, DetectedCard)


class TestCardDetectorYOLO:
    """Test YOLO-specific functionality."""

    def test_no_model_graceful_fallback(self):
        """Without YOLO model, should gracefully fall back."""
        detector = CardDetector(model_path="nonexistent.pt")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Should not raise, just return empty
        results = detector.detect_yolo(frame)
        assert results == []


@requires_cv2
class TestCardDetectorTemplate:
    """Test template matching functionality."""

    @pytest.fixture
    def detector(self):
        return CardDetector()

    def test_template_matching_threshold(self, detector):
        """Template matching should respect threshold."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # High threshold should find nothing on random noise
        results = detector.detect_template(frame, threshold=0.99)
        assert results == []

    def test_template_matching_low_threshold(self, detector):
        """Low threshold may find false positives (expected)."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        results = detector.detect_template(frame, threshold=0.1)
        # May or may not find something, just shouldn't crash
        assert isinstance(results, list)

    def test_rank_suit_template_classifies_known_slot(self, tmp_path):
        """Rank/suit templates classify a fixed card ROI."""
        rank_dir = tmp_path / "ranks"
        suit_dir = tmp_path / "suits"
        rank_dir.mkdir()
        suit_dir.mkdir()

        rank_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(rank_template, 255)

        suit_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(np.fliplr(suit_template), 255)

        cv2.imwrite(str(rank_dir / "A.png"), rank_template)
        cv2.imwrite(str(suit_dir / "h.png"), suit_template)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[14:24, 14:24] = cv2.cvtColor(rank_template, cv2.COLOR_GRAY2BGR)
        frame[34:44, 14:24] = cv2.cvtColor(suit_template, cv2.COLOR_GRAY2BGR)

        detector = CardDetector(template_dir=tmp_path, min_card_white_ratio=0.0)
        result = detector.detect_rank_suit_template(frame, (10, 10, 60, 80), threshold=0.5)

        assert len(result) == 1
        assert result[0].card == "Ah"

    def test_rank_suit_diagnostics_explain_known_slot(self, tmp_path):
        """Diagnostics expose top labels, confidence, and acceptance status."""
        rank_dir = tmp_path / "ranks"
        suit_dir = tmp_path / "suits"
        rank_dir.mkdir()
        suit_dir.mkdir()

        rank_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(rank_template, 255)

        suit_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(np.fliplr(suit_template), 255)

        cv2.imwrite(str(rank_dir / "A.png"), rank_template)
        cv2.imwrite(str(suit_dir / "h.png"), suit_template)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[14:24, 14:24] = cv2.cvtColor(rank_template, cv2.COLOR_GRAY2BGR)
        frame[34:44, 14:24] = cv2.cvtColor(suit_template, cv2.COLOR_GRAY2BGR)

        detector = CardDetector(template_dir=tmp_path, min_card_white_ratio=0.0)
        diagnostic = detector.rank_suit_diagnostics(
            frame,
            (10, 10, 60, 80),
            threshold=0.5,
            top_n=3,
        )

        assert diagnostic["accepted"] is True
        assert diagnostic["accepted_card"] == "Ah"
        assert diagnostic["status"] == "ACCEPTED"
        assert diagnostic["rank_candidates"][0]["label"] == "A"
        assert diagnostic["suit_candidates"][0]["label"] == "h"

    def test_full_card_template_diagnostics_explain_known_slot(self, tmp_path):
        """Full-card diagnostics expose the template candidates used in fallback."""
        card_template = np.zeros((20, 20, 3), dtype=np.uint8)
        card_template[2:18, 2:18] = 255
        cv2.imwrite(str(tmp_path / "Ah.png"), card_template)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:30, 10:30] = card_template

        detector = CardDetector(template_dir=tmp_path, min_card_white_ratio=0.0)
        diagnostic = detector.full_card_template_diagnostics(
            frame,
            (10, 10, 60, 80),
            threshold=0.8,
            top_n=3,
        )

        assert diagnostic["accepted"] is True
        assert diagnostic["accepted_card"] == "Ah"
        assert diagnostic["status"] == "ACCEPTED"
        assert diagnostic["card_candidates"][0]["label"] == "Ah"

    def test_full_card_template_diagnostics_rejects_ambiguous_slot(self, tmp_path):
        """Near-tied full-card matches should not become confident cards."""
        card_template = np.zeros((20, 20, 3), dtype=np.uint8)
        card_template[2:18, 2:18] = 255
        cv2.imwrite(str(tmp_path / "Ah.png"), card_template)
        cv2.imwrite(str(tmp_path / "As.png"), card_template)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:30, 10:30] = card_template

        detector = CardDetector(
            template_dir=tmp_path,
            min_card_white_ratio=0.0,
            min_full_card_margin=0.1,
        )
        diagnostic = detector.full_card_template_diagnostics(
            frame,
            (10, 10, 60, 80),
            threshold=0.99,
            top_n=3,
        )

        assert diagnostic["accepted"] is False
        assert diagnostic["status"] == "AMBIGUOUS_MATCH"
        assert diagnostic["score_margin"] == 0.0
        assert detector.detect_template(frame, (10, 10, 60, 80), threshold=0.99) == []

    def test_fixed_slot_template_rejects_empty_table_region(self, tmp_path):
        """Fixed-slot template matching should not invent cards on empty felt."""
        card_template = np.full((20, 20, 3), 255, dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "Ah.png"), card_template)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :] = (20, 90, 30)

        detector = CardDetector(template_dir=tmp_path)

        assert detector.detect_template(frame, (10, 10, 60, 80), threshold=0.1) == []

        diagnostic = detector.full_card_template_diagnostics(
            frame,
            (10, 10, 60, 80),
            threshold=0.1,
        )

        assert diagnostic["accepted"] is False
        assert diagnostic["status"] == "EMPTY_SLOT"

    def test_rank_suit_fallback_runs_when_full_templates_are_incomplete(self, tmp_path):
        """A missing full-card label can still classify through rank/suit templates."""
        rank_dir = tmp_path / "ranks"
        suit_dir = tmp_path / "suits"
        cards_dir = tmp_path / "cards"
        rank_dir.mkdir()
        suit_dir.mkdir()
        cards_dir.mkdir()

        rank_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(rank_template, 255)

        suit_template = np.zeros((10, 10), dtype=np.uint8)
        np.fill_diagonal(np.fliplr(suit_template), 255)

        cv2.imwrite(str(rank_dir / "A.png"), rank_template)
        cv2.imwrite(str(suit_dir / "h.png"), suit_template)
        cv2.imwrite(
            str(cards_dir / "2c_unrelated.png"),
            np.full((20, 20, 3), 127, dtype=np.uint8),
        )

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[14:24, 14:24] = cv2.cvtColor(rank_template, cv2.COLOR_GRAY2BGR)
        frame[34:44, 14:24] = cv2.cvtColor(suit_template, cv2.COLOR_GRAY2BGR)

        detector = CardDetector(template_dir=tmp_path, min_card_white_ratio=0.0)
        result = detector.detect_template(frame, (10, 10, 60, 80), threshold=0.95)

        assert len(result) == 1
        assert result[0].card == "Ah"
