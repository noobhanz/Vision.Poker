from engine.models import GameState
from pipeline.stability import StateStabilizer


def _state(hero=None, board=None, pot=0.03):
    return GameState(
        hero_cards=hero or ["Ah", "Kh"],
        board_cards=board or [],
        pot_size=pot,
        bet_to_call=0.02,
        hero_stack=2.0,
        action_mode="decision",
        legal_actions=["fold", "call", "raise"],
        action_amounts={"call": 0.02, "raise": 0.04},
        confidence=0.95,
    )


def test_stabilizer_requires_repeated_same_key():
    stabilizer = StateStabilizer(stable_frames_required=2)

    first = stabilizer.observe(_state(), "OK")
    second = stabilizer.observe(_state(), "OK")

    assert first.count == 1
    assert first.is_stable is False
    assert second.count == 2
    assert second.is_stable is True


def test_stabilizer_resets_count_when_state_changes():
    stabilizer = StateStabilizer(stable_frames_required=2)

    assert stabilizer.observe(_state(), "OK").count == 1
    assert stabilizer.observe(_state(board=["2h", "7d", "Qs"]), "OK").count == 1


def test_stabilizer_reset_clears_pending_state():
    stabilizer = StateStabilizer(stable_frames_required=2)
    stabilizer.observe(_state(), "OK")

    stabilizer.reset()

    assert stabilizer.pending_key is None
    assert stabilizer.pending_count == 0
