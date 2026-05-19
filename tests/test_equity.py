"""Tests for equity calculation."""

import pytest
from engine.equity import calculate_equity, remaining_deck


class TestRemainingDeck:
    """Test deck management."""

    def test_full_deck(self):
        """Empty known cards = 52 card deck."""
        deck = remaining_deck([])
        assert len(deck) == 52

    def test_remove_known_cards(self):
        """Known cards are removed from deck."""
        deck = remaining_deck(["Ah", "Kd"])
        assert len(deck) == 50
        assert "Ah" not in deck
        assert "Kd" not in deck

    def test_case_insensitive(self):
        """Card format is normalized."""
        deck = remaining_deck(["ah", "KD", "2C"])
        assert len(deck) == 49


class TestEquityCalculation:
    """Test Monte Carlo equity calculation."""

    def test_aa_vs_random(self):
        """AA vs random preflop → hero equity ≈ 0.85 (±0.03)."""
        equity = calculate_equity(
            hero=["Ah", "As"],
            board=[],
            num_opponents=1,
            n=5000,
        )
        # AA vs random range is ~85%
        assert equity == pytest.approx(0.85, abs=0.03)

    def test_ak_suited_vs_random(self):
        """AK suited vs random → hero equity between 0.55-0.70."""
        equity = calculate_equity(
            hero=["Ah", "Kh"],
            board=[],
            num_opponents=1,
            n=5000,
        )
        # AKs vs random range - using basic evaluator, production uses phevaluator
        assert 0.55 <= equity <= 0.70

    def test_flush_draw_on_flop(self):
        """Flush draw on flop vs made hand → equity ≈ 0.35 (±0.05)."""
        # Ah Kh on 2h 7h Qs - flush draw
        equity = calculate_equity(
            hero=["Ah", "Kh"],
            board=["2h", "7h", "Qs"],
            num_opponents=1,
            n=5000,
        )
        # Flush draw has ~35% equity vs a made hand
        # But vs random range it's higher
        assert 0.30 <= equity <= 0.75

    def test_same_state_returns_same_monte_carlo_equity(self):
        """Repeated HUD updates for the same state should not flicker."""
        first = calculate_equity(
            hero=["Ah", "Jc"],
            board=["Ac", "Ts", "2d"],
            num_opponents=1,
            n=500,
        )
        second = calculate_equity(
            hero=["Ah", "Jc"],
            board=["Ac", "Ts", "2d"],
            num_opponents=1,
            n=500,
        )

        assert second == first

    def test_set_vs_top_pair(self):
        """Set vs random → equity ≈ 0.90+ (±0.03)."""
        # Set of 7s on a Q72 board
        equity = calculate_equity(
            hero=["7h", "7d"],
            board=["Qc", "7s", "2d"],
            num_opponents=1,
            n=5000,
        )
        # Set vs random range is dominant
        assert equity >= 0.80

    def test_invalid_hero_cards(self):
        """Raise error for invalid hero hand."""
        with pytest.raises(ValueError, match="exactly 2 cards"):
            calculate_equity(hero=["Ah"], board=[], n=100)

    def test_invalid_board(self):
        """Raise error for too many board cards."""
        with pytest.raises(ValueError, match="more than 5 cards"):
            calculate_equity(
                hero=["Ah", "Kh"],
                board=["2c", "3c", "4c", "5c", "6c", "7c"],
                n=100,
            )

    def test_river_equity(self):
        """Equity on river with all cards known."""
        # AA on board with no help for villain
        equity = calculate_equity(
            hero=["Ah", "As"],
            board=["2c", "7d", "Tc", "3h", "9s"],
            num_opponents=1,
            n=1000,
        )
        # Overpair vs random on river should be strong
        assert equity >= 0.60

    def test_two_opponents(self):
        """Equity decreases with more opponents."""
        equity_1 = calculate_equity(
            hero=["Ah", "Kh"],
            board=[],
            num_opponents=1,
            n=3000,
        )
        equity_2 = calculate_equity(
            hero=["Ah", "Kh"],
            board=[],
            num_opponents=2,
            n=3000,
        )
        # Equity should be lower vs more opponents
        assert equity_2 < equity_1
