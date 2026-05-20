from engine.models import DrawType, Metrics
from capture.window_finder import WindowRect
from overlay.hud import call_edge_style, call_metric_display, ev_style, hud_position_for_rect


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

    assert pot_label == "N/A"
    assert req_label == "N/A"
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


def test_call_edge_style_is_red_when_equity_misses_price():
    assert call_edge_style(_metrics(equity=0.24, required_equity=0.25)) == "negative"


def test_call_edge_style_is_yellow_for_thin_profitable_calls():
    assert call_edge_style(_metrics(equity=0.28, required_equity=0.25)) == "warning"


def test_call_edge_style_is_green_for_clear_profitable_calls():
    assert call_edge_style(_metrics(equity=0.31, required_equity=0.25)) == "positive"


def test_ev_style_uses_negative_thin_positive_and_clear_positive_buckets():
    assert ev_style(-0.01) == "negative"
    assert ev_style(0.00) == "warning"
    assert ev_style(0.02) == "positive"


def test_standalone_hud_position_stays_visible_when_right_side_is_offscreen():
    x, y = hud_position_for_rect(
        WindowRect(x=80, y=40, width=955, height=688),
        hud_width=340,
        hud_height=400,
        standalone=True,
        position_preference="top-right",
        screen_width=1280,
        screen_height=800,
    )

    assert x == 930
    assert y == 40


def test_standalone_hud_position_clamps_when_no_side_has_room():
    x, y = hud_position_for_rect(
        WindowRect(x=0, y=0, width=1200, height=700),
        hud_width=340,
        hud_height=400,
        standalone=True,
        position_preference="top-right",
        screen_width=1280,
        screen_height=800,
    )

    assert x == 930
    assert y == 10
