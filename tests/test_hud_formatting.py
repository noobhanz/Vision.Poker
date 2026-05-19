from engine.models import DrawType, Metrics
from overlay.hud import call_metric_display


def _metrics(**overrides):
    values = {
        "equity": 0.45,
        "pot_odds": 0.0,
        "required_equity": 0.0,
        "ev_call": 0.03,
        "ev_fold": 0.0,
        "outs": 0,
        "draw_type": DrawType.NONE,
        "made_hand_rank": "High Card",
        "recommendation": "CALL",
        "confidence": 0.9,
        "action_mode": "decision",
    }
    values.update(overrides)
    return Metrics(**values)


def test_call_metric_display_shows_no_call_when_required_equity_is_zero():
    pot_label, req_label, pot_value, req_value = call_metric_display(_metrics())

    assert pot_label == "No call"
    assert req_label == "No call"
    assert pot_value is None
    assert req_value is None


def test_call_metric_display_hides_values_when_waiting():
    pot_label, req_label, pot_value, req_value = call_metric_display(
        _metrics(
            action_mode="none",
            recommendation="WAIT",
            parse_status="NO_ACTIVE_HERO_CARDS",
        )
    )

    assert pot_label == "--"
    assert req_label == "--"
    assert pot_value is None
    assert req_value is None


def test_call_metric_display_returns_percent_values_for_call_decision():
    pot_label, req_label, pot_value, req_value = call_metric_display(
        _metrics(pot_odds=0.25, required_equity=0.25)
    )

    assert pot_label == ""
    assert req_label == ""
    assert pot_value == 0.25
    assert req_value == 0.25
