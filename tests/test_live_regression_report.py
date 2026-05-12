from pathlib import Path

import pytest

from engine.models import GameState
from tools.live_regression_report import (
    _is_suspicious_money,
    summarize_live_frames,
)


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
