from pathlib import Path

from tools.bootstrap_annotations import (
    candidate_from_state,
    candidate_path_for,
    candidate_rejection_reason,
    has_strict_annotation,
)


def test_candidate_path_uses_non_strict_suffix():
    assert (
        candidate_path_for(Path("fixtures/pokerstars_023.png"))
        == Path("fixtures/pokerstars_023.candidate.json")
    )


def test_has_strict_annotation_ignores_candidate_sidecar(tmp_path):
    frame = tmp_path / "pokerstars_023.png"
    frame.write_bytes(b"image")
    frame.with_suffix(".candidate.json").write_text("{}")

    assert has_strict_annotation(frame) is False

    frame.with_suffix(".json").write_text("{}")
    assert has_strict_annotation(frame) is True


def test_candidate_payload_keeps_review_metadata():
    state = {
        "hero_cards": ["Ah", "Kh"],
        "board_cards": ["2h", "7h", "Qs"],
        "pot_size": 0.25,
        "bet_to_call": 0.05,
        "hero_stack": 1.75,
        "street": "flop",
        "action_mode": "decision",
        "legal_actions": ["fold", "call", "raise"],
        "action_amounts": {"call": 0.05, "raise": 0.15},
    }

    candidate = candidate_from_state("pokerstars_023.png", state, "OK")

    assert candidate["_candidate"]["review_required"] is True
    assert candidate["_candidate"]["schema_version"] == 1
    assert candidate["hero_cards"] == ["Ah", "Kh"]
    assert candidate["board_cards"] == ["2h", "7h", "Qs"]
    assert candidate["bet_to_call"] == 0.05
    assert candidate["legal_actions"] == ["fold", "call", "raise"]
    assert candidate["action_amounts"] == {"call": 0.05, "raise": 0.15}


def test_candidate_payload_can_record_parser_commit():
    state = {
        "hero_cards": ["Ah", "Kh"],
        "board_cards": [],
        "pot_size": 0.03,
        "hero_stack": 1.75,
        "street": "preflop",
        "action_mode": "preselect",
    }

    candidate = candidate_from_state(
        "pokerstars_023.png",
        state,
        "OK",
        parser_commit="abc123",
    )

    assert candidate["_candidate"]["parser_commit"] == "abc123"


def test_candidate_rejection_rejects_partial_board_detections():
    state = {
        "board_cards": ["Ah", "Kd"],
    }

    assert candidate_rejection_reason(state, "OK") == "partial_board_detected_2"


def test_candidate_rejection_rejects_non_ok_parse_status():
    state = {
        "board_cards": [],
    }

    assert (
        candidate_rejection_reason(state, "LOW_CONFIDENCE")
        == "parse_status_LOW_CONFIDENCE"
    )


def test_candidate_rejection_accepts_real_streets():
    assert candidate_rejection_reason({"board_cards": []}, "OK") is None
    assert candidate_rejection_reason({"board_cards": ["Ah", "Kd", "Qs"]}, "OK") is None
    assert (
        candidate_rejection_reason({"board_cards": ["Ah", "Kd", "Qs", "2c"]}, "OK")
        is None
    )
    assert (
        candidate_rejection_reason(
            {"board_cards": ["Ah", "Kd", "Qs", "2c", "3d"]},
            "OK",
        )
        is None
    )
