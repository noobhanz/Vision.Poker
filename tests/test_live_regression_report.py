from pathlib import Path

import cv2
import pytest

from engine.models import GameState
from tools.live_regression_report import (
    _is_suspicious_money,
    _slot_diagnostics,
    summarize_live_frames,
)
from vision.card_detector import CardDetector
from vision.roi_config import load_skin_config


def test_suspicious_money_checks_all_money_fields():
    state = GameState(
        hero_cards=["Ah", "Kh"],
        board_cards=[],
        pot_size=0.03,
        bet_to_call=0.02,
        hero_stack=2.0,
        villain_stacks=[1.98],
        action_amounts={"raise": 0.04},
    )

    assert _is_suspicious_money(state, 10.0) is False

    state.hero_stack = 70.0
    assert _is_suspicious_money(state, 10.0) is True


def test_live_report_rejects_empty_frame_directory(tmp_path):
    with pytest.raises(ValueError, match="No image files"):
        summarize_live_frames(Path(tmp_path))


def test_slot_diagnostics_explain_live_warning_frame():
    frame_path = Path(
        "tests/fixtures/live_sequences/pokerstars_live_smoke/"
        "live_smoke_009_board_warning.png"
    )
    frame = cv2.imread(str(frame_path))
    assert frame is not None

    config = load_skin_config("pokerstars_mac_cash").scale_to_window(
        frame.shape[1],
        frame.shape[0],
    )

    diagnostics = _slot_diagnostics(frame, config, CardDetector())

    assert "hero_card_1" in diagnostics
    assert "board_card_1" in diagnostics
    assert diagnostics["hero_card_1"]["accepted"] is False
    assert diagnostics["hero_card_1"]["full_card_status"] == "AMBIGUOUS_MATCH"
    assert "full_card_status" in diagnostics["board_card_1"]
    assert "rank_candidates" in diagnostics["board_card_1"]


def test_pokerstars_live_smoke_fixture_summary():
    summary = summarize_live_frames(
        Path("tests/fixtures/live_sequences/pokerstars_live_smoke"),
        stable_frames=2,
        monte_carlo_n=5,
    )

    assert summary["frames"]["total"] == 9
    assert summary["frames"]["active"] == 6
    assert summary["frames"]["published_ok"] == 3
    assert summary["frames"]["published_warnings"] == 0
    assert summary["frames"]["actionable_published_ok"] == 2
    assert summary["status_counts"] == {
        "OK": 6,
        "INCOMPLETE_HERO_CARDS": 2,
        "NO_ACTIVE_HERO_CARDS": 1,
    }
    assert summary["published_status_counts"] == {
        "OK": 3,
    }
    assert summary["suspicious_published_ok_count"] == 0
    warning = summary["warning_samples"]["INCOMPLETE_HERO_CARDS"][0]
    assert "card_slots" not in warning


def test_pokerstars_live_smoke_fixture_can_include_card_diagnostics():
    summary = summarize_live_frames(
        Path("tests/fixtures/live_sequences/pokerstars_live_smoke"),
        stable_frames=2,
        monte_carlo_n=5,
        include_card_diagnostics=True,
    )

    warning = summary["warning_samples"]["INCOMPLETE_HERO_CARDS"][0]
    assert "card_slots" in warning
    assert "hero_card_1" in warning["card_slots"]
