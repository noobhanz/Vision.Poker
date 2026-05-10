"""Tests for expected value calculations."""

import pytest
from engine.ev import ev_call, ev_fold, recommendation


class TestEVCall:
    """Test EV(call) calculation."""

    def test_positive_ev(self):
        """50% equity with good pot odds = positive EV."""
        # Equity 50%, pot $100, call $25
        # EV = 0.50 * 125 - 25 = 62.5 - 25 = 37.5
        result = ev_call(0.50, 100, 25)
        assert result == pytest.approx(37.5, abs=0.01)

    def test_negative_ev(self):
        """Low equity with bad pot odds = negative EV."""
        # Equity 10%, pot $100, call $100
        # EV = 0.10 * 200 - 100 = 20 - 100 = -80
        result = ev_call(0.10, 100, 100)
        assert result == pytest.approx(-80.0, abs=0.01)

    def test_breakeven_ev(self):
        """EV = 0 when equity equals required equity."""
        # Equity 20%, pot $100, call $25 (required = 20%)
        # EV = 0.20 * 125 - 25 = 25 - 25 = 0
        result = ev_call(0.20, 100, 25)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_high_equity(self):
        """High equity = high positive EV."""
        # Equity 80%, pot $100, call $50
        # EV = 0.80 * 150 - 50 = 120 - 50 = 70
        result = ev_call(0.80, 100, 50)
        assert result == pytest.approx(70.0, abs=0.01)


class TestEVFold:
    """Test EV(fold) calculation."""

    def test_ev_fold_is_zero(self):
        """Folding always has EV of 0."""
        assert ev_fold() == 0.0


class TestRecommendation:
    """Test recommendation logic."""

    def test_fold_recommendation(self):
        """Recommend fold when EV is negative and equity below required."""
        result = recommendation(-50, 0.10, 0.30)
        assert result == "FOLD"

    def test_call_recommendation(self):
        """Recommend call when EV is positive."""
        result = recommendation(10, 0.25, 0.20)
        assert result == "CALL"

    def test_raise_candidate(self):
        """Recommend raise when equity significantly exceeds required."""
        # 50% equity vs 20% required = 30 point margin > 15
        result = recommendation(50, 0.50, 0.20)
        assert result == "RAISE CANDIDATE"

    def test_marginal_call(self):
        """Call when equity slightly above required."""
        # 25% equity vs 20% required = 5 point margin < 15
        result = recommendation(5, 0.25, 0.20)
        assert result == "CALL"

    def test_borderline_raise(self):
        """Raise candidate when equity well above required."""
        # 40% equity vs 20% required = 20 point margin > 15
        result = recommendation(30, 0.40, 0.20)
        assert result == "RAISE CANDIDATE"
