"""Tests for pot odds calculations."""

import pytest
from engine.pot_odds import pot_odds, required_equity, is_call_profitable


class TestPotOdds:
    """Test pot odds calculation."""

    def test_pot_100_call_25(self):
        """Pot=$100, call=$25 → pot_odds=0.20"""
        result = pot_odds(100, 25)
        assert result == pytest.approx(0.20, abs=0.001)

    def test_pot_50_call_50(self):
        """Pot=$50, call=$50 → pot_odds=0.50"""
        result = pot_odds(50, 50)
        assert result == pytest.approx(0.50, abs=0.001)

    def test_pot_200_call_10(self):
        """Pot=$200, call=$10 → pot_odds≈0.047"""
        result = pot_odds(200, 10)
        assert result == pytest.approx(0.0476, abs=0.001)

    def test_zero_bet_to_call(self):
        """Zero bet to call returns 0."""
        result = pot_odds(100, 0)
        assert result == 0.0

    def test_negative_bet_to_call(self):
        """Negative bet to call returns 0."""
        result = pot_odds(100, -10)
        assert result == 0.0


class TestRequiredEquity:
    """Test required equity calculation."""

    def test_pot_100_call_25(self):
        """Required equity equals pot odds."""
        result = required_equity(100, 25)
        assert result == pytest.approx(0.20, abs=0.001)

    def test_pot_50_call_50(self):
        """50% pot = 50% required equity."""
        result = required_equity(50, 50)
        assert result == pytest.approx(0.50, abs=0.001)


class TestIsCallProfitable:
    """Test call profitability check."""

    def test_equity_above_required(self):
        """Call is profitable when equity > required."""
        # 30% equity, 20% required
        assert is_call_profitable(0.30, 100, 25) is True

    def test_equity_below_required(self):
        """Call is not profitable when equity < required."""
        # 15% equity, 20% required
        assert is_call_profitable(0.15, 100, 25) is False

    def test_equity_equals_required(self):
        """Call is breakeven when equity = required."""
        # 20% equity, 20% required
        assert is_call_profitable(0.20, 100, 25) is True
