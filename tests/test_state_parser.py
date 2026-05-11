import cv2

from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser


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
