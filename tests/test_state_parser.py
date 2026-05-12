import numpy as np
import pytest

from vision.card_detector import CardDetector
from vision.card_detector import DetectedCard
from vision.action_reader import ActionState
from vision.ocr_engine import OCREngine
from vision.roi_config import ROIConfig, ROIRegion, load_skin_config
from vision.state_parser import StateParser

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


requires_cv2 = pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not installed")


class StubCardDetector:
    def __init__(self):
        self.cards = iter([
            DetectedCard("Ah", 0.95, (0, 0, 10, 10)),
            DetectedCard("Kd", 0.95, (0, 0, 10, 10)),
        ])

    def detect(self, frame, roi):
        return [next(self.cards)]


class StubOCREngine:
    def read_number(self, frame, roi):
        return 1.25


def test_visible_call_with_unknown_amount_returns_parse_warning(monkeypatch):
    parser = StateParser(StubCardDetector(), StubOCREngine())
    monkeypatch.setattr(
        parser.action_reader,
        "read",
        lambda frame, roi: ActionState(
            legal_actions=["fold", "call", "raise"],
            mode="decision",
            amount_unknown=True,
            confidence=0.9,
        ),
    )
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
        pot_size=ROIRegion(0, 20, 10, 10),
        action_buttons=ROIRegion(0, 40, 100, 40),
    )

    state, status = parser.parse_with_fallback(
        np.zeros((100, 120, 3), dtype=np.uint8),
        config,
        min_confidence=0.6,
    )

    assert state is not None
    assert status == "ACTION_AMOUNT_UNKNOWN"
    assert state.action_amount_unknown is True
    assert state.bet_to_call == 0.0


class DuplicateCardDetector:
    def __init__(self):
        self.cards = iter([
            DetectedCard("Ah", 0.95, (0, 0, 10, 10)),
            DetectedCard("Ah", 0.90, (0, 0, 10, 10)),
        ])

    def detect(self, frame, roi):
        return [next(self.cards)]


class MissingSecondCardDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, frame, roi):
        self.calls += 1
        if self.calls == 1:
            return [DetectedCard("Ah", 0.95, (0, 0, 10, 10))]
        return []


class NoHeroCardsDetector:
    def detect(self, frame, roi):
        return []


class PartialBoardDetector:
    def __init__(self):
        self.cards = iter([
            DetectedCard("Ah", 0.95, (0, 0, 10, 10)),
            DetectedCard("Kd", 0.95, (0, 0, 10, 10)),
            DetectedCard("2c", 0.91, (0, 0, 10, 10)),
        ])

    def detect(self, frame, roi):
        try:
            return [next(self.cards)]
        except StopIteration:
            return []


def test_parse_with_fallback_reports_no_active_hero_cards_for_empty_hero_rois():
    parser = StateParser(NoHeroCardsDetector(), StubOCREngine())
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
    )

    state, status = parser.parse_with_fallback(
        np.zeros((100, 120, 3), dtype=np.uint8),
        config,
    )

    assert state is None
    assert status == "NO_ACTIVE_HERO_CARDS"


def test_parse_with_fallback_reports_duplicate_cards():
    parser = StateParser(DuplicateCardDetector(), StubOCREngine())
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
    )

    state, status = parser.parse_with_fallback(
        np.zeros((100, 120, 3), dtype=np.uint8),
        config,
    )

    assert state is None
    assert status == "DUPLICATE_CARDS"


def test_parse_with_fallback_reports_incomplete_hero_cards():
    parser = StateParser(MissingSecondCardDetector(), StubOCREngine())
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
    )

    state, status = parser.parse_with_fallback(
        np.zeros((100, 120, 3), dtype=np.uint8),
        config,
    )

    assert state is None
    assert status == "INCOMPLETE_HERO_CARDS"


def test_parse_with_fallback_warns_on_partial_board_detection():
    parser = StateParser(PartialBoardDetector(), StubOCREngine())
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
        board_card_1=ROIRegion(20, 0, 10, 10),
        board_card_2=ROIRegion(30, 0, 10, 10),
        board_card_3=ROIRegion(40, 0, 10, 10),
        pot_size=ROIRegion(0, 20, 10, 10),
    )

    state, status = parser.parse_with_fallback(
        np.zeros((100, 120, 3), dtype=np.uint8),
        config,
    )

    assert state is not None
    assert status == "PARTIAL_BOARD_DETECTED_1"
    assert state.hero_cards == ["Ah", "Kd"]
    assert state.board_cards == ["2c"]


@requires_cv2
def test_overlapped_hero_cards_use_unique_assignment():
    """The overlapped preflop fixture should parse as Jc Js, not duplicate Js."""
    frame = cv2.imread("tests/fixtures/sample_frames/pokerstars/pokerstars_020.png")
    config = load_skin_config("pokerstars_mac_cash").scale_to_window(
        frame.shape[1],
        frame.shape[0],
    )

    parser = StateParser(CardDetector(), OCREngine())
    state, status = parser.parse_with_fallback(frame, config, min_confidence=0.5)

    assert status == "OK"
    assert state is not None
    assert state.hero_cards == ["Jc", "Js"]
    assert state.board_cards == []
    assert state.pot_size == 0.42
    assert state.action_mode == "none"
