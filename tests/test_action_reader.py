import pytest
import numpy as np

from vision.action_reader import ActionReader
from vision.roi_config import load_skin_config

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

requires_cv2 = pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not installed")


FIXTURE_DIR = "tests/fixtures/sample_frames/pokerstars"


def _read_actions(frame_name: str):
    frame = cv2.imread(f"{FIXTURE_DIR}/{frame_name}")
    config = load_skin_config("pokerstars_mac_cash").scale_to_window(
        frame.shape[1],
        frame.shape[0],
    )
    return ActionReader().read(frame, config.action_buttons.as_tuple())


def test_call_button_with_unreadable_amount_is_marked_unknown(monkeypatch):
    reader = ActionReader()
    frame = np.zeros((120, 240, 3), dtype="uint8")

    monkeypatch.setattr(
        reader,
        "_find_red_buttons",
        lambda frame, roi: [(0, 60, 70, 40), (80, 60, 70, 40), (160, 60, 70, 40)],
    )
    monkeypatch.setattr(reader, "_is_red_button", lambda frame, roi: 0.9)
    monkeypatch.setattr(reader, "_classify_call_or_check", lambda frame, roi: "call")
    monkeypatch.setattr(reader, "_classify_raise_or_bet", lambda frame, roi: "raise")
    monkeypatch.setattr(reader.ocr_engine, "read_number", lambda frame, roi: None)

    actions = reader.read(frame, (0, 0, 240, 120))

    assert actions.mode == "decision"
    assert actions.legal_actions == ["fold", "call", "raise"]
    assert actions.bet_to_call is None
    assert actions.amount_unknown is True


@requires_cv2
def test_reads_call_and_raise_buttons():
    actions = _read_actions("pokerstars_001.png")

    assert actions.legal_actions == ["fold", "call", "raise"]
    assert actions.mode == "decision"
    assert actions.bet_to_call == 0.02
    assert actions.action_amounts["call"] == 0.02
    assert actions.action_amounts["raise"] == 0.04


@requires_cv2
def test_reads_check_and_bet_buttons_without_false_call():
    actions = _read_actions("pokerstars_010.png")

    assert actions.legal_actions == ["check", "bet"]
    assert actions.mode == "decision"
    assert actions.bet_to_call == 0.0


@requires_cv2
def test_marks_checkbox_only_area_as_preselect():
    actions = _read_actions("pokerstars_008.png")

    assert actions.mode == "preselect"
    assert actions.legal_actions == []
    assert actions.bet_to_call is None
    assert actions.preaction_count >= 2
