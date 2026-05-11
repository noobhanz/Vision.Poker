import cv2

from vision.action_reader import ActionReader
from vision.roi_config import load_skin_config


FIXTURE_DIR = "tests/fixtures/sample_frames/pokerstars"


def _read_actions(frame_name: str):
    frame = cv2.imread(f"{FIXTURE_DIR}/{frame_name}")
    config = load_skin_config("pokerstars_mac_cash").scale_to_window(
        frame.shape[1],
        frame.shape[0],
    )
    return ActionReader().read(frame, config.action_buttons.as_tuple())


def test_reads_call_and_raise_buttons():
    actions = _read_actions("pokerstars_001.png")

    assert actions.legal_actions == ["fold", "call", "raise"]
    assert actions.mode == "decision"
    assert actions.bet_to_call == 0.02
    assert actions.action_amounts["call"] == 0.02
    assert actions.action_amounts["raise"] == 0.04


def test_reads_check_and_bet_buttons_without_false_call():
    actions = _read_actions("pokerstars_010.png")

    assert actions.legal_actions == ["check", "bet"]
    assert actions.mode == "decision"
    assert actions.bet_to_call == 0.0


def test_marks_checkbox_only_area_as_preselect():
    actions = _read_actions("pokerstars_008.png")

    assert actions.mode == "preselect"
    assert actions.legal_actions == []
    assert actions.bet_to_call is None
    assert actions.preaction_count >= 2
