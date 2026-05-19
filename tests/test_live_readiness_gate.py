from pathlib import Path

from tools.live_readiness_gate import (
    _parse_streets,
    evaluate_live_readiness,
)
from tools.live_regression_report import summarize_live_frames


def _base_report():
    return {
        "frames": {
            "published_ok": 3,
            "actionable_published_ok": 2,
        },
        "rates": {
            "published_warning_rate": 0.03,
        },
        "published_status_counts": {
            "OK": 3,
        },
        "published_street_counts": {
            "preflop": 2,
            "flop": 1,
        },
        "suspicious_published_ok_count": 0,
    }


def test_parse_required_streets():
    assert _parse_streets("preflop, flop, river") == {
        "preflop",
        "flop",
        "river",
    }
    assert _parse_streets("") == set()


def test_evaluate_live_readiness_passes_clean_report():
    gate = evaluate_live_readiness(
        _base_report(),
        max_published_warning_rate=0.05,
        min_published_ok=1,
        min_actionable_published_ok=1,
        required_published_streets={"preflop", "flop"},
    )

    assert gate["passed"] is True
    assert gate["failures"] == []


def test_evaluate_live_readiness_reports_failures():
    report = _base_report()
    report["suspicious_published_ok_count"] = 1
    report["rates"]["published_warning_rate"] = 0.4
    report["frames"]["published_ok"] = 0

    gate = evaluate_live_readiness(
        report,
        max_suspicious_published_ok=0,
        max_published_warning_rate=0.05,
        min_published_ok=1,
        min_actionable_published_ok=3,
        required_published_streets={"preflop", "turn"},
    )

    failure_checks = {failure["check"] for failure in gate["failures"]}
    assert gate["passed"] is False
    assert failure_checks == {
        "suspicious_published_ok_count",
        "published_warning_rate",
        "published_ok",
        "actionable_published_ok",
        "required_published_streets",
    }


def test_live_smoke_fixture_passes_current_readiness_gate():
    report = summarize_live_frames(
        Path("tests/fixtures/live_sequences/pokerstars_live_smoke"),
        stable_frames=2,
        monte_carlo_n=5,
    )

    gate = evaluate_live_readiness(
        report,
        max_published_warning_rate=0.25,
        min_published_ok=3,
        min_actionable_published_ok=2,
        required_published_streets={"preflop", "flop", "river"},
    )

    assert gate["passed"] is True


def test_live_smoke_fixture_fails_tight_warning_gate():
    report = summarize_live_frames(
        Path("tests/fixtures/live_sequences/pokerstars_live_smoke"),
        stable_frames=2,
        monte_carlo_n=5,
    )

    gate = evaluate_live_readiness(report, max_published_warning_rate=0.0)

    assert gate["passed"] is False
    assert gate["failures"][0]["check"] == "published_warning_rate"
