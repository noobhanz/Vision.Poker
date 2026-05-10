"""Tests for draw detection and classification."""

import pytest
from engine.draws import count_outs, classify_draw, made_hand_description
from engine.models import DrawType


class TestFlushDraw:
    """Test flush draw detection."""

    def test_flush_draw_9_outs(self):
        """Ah Kh on 2h 7h Qs → flush_draw, 9 outs."""
        hero = ["Ah", "Kh"]
        board = ["2h", "7h", "Qs"]

        draw = classify_draw(hero, board)
        outs = count_outs(hero, board)

        assert draw == DrawType.FLUSH_DRAW
        assert outs == 9

    def test_no_flush_draw(self):
        """No flush draw with only 3 suited cards."""
        hero = ["Ah", "Kd"]
        board = ["2h", "7c", "Qs"]

        draw = classify_draw(hero, board)
        outs = count_outs(hero, board)

        assert draw != DrawType.FLUSH_DRAW
        assert outs == 0

    def test_made_flush_not_draw(self):
        """Made flush is not classified as draw."""
        hero = ["Ah", "Kh"]
        board = ["2h", "7h", "Qh"]

        draw = classify_draw(hero, board)
        # Already have flush, no draw
        assert draw == DrawType.NONE


class TestStraightDraw:
    """Test straight draw detection."""

    def test_oesd_8_outs(self):
        """9c Tc on 8h Jd 2s → OESD, 8 outs."""
        hero = ["9c", "Tc"]
        board = ["8h", "Jd", "2s"]

        draw = classify_draw(hero, board)
        outs = count_outs(hero, board)

        assert draw == DrawType.OESD
        assert outs == 8

    def test_gutshot_4_outs(self):
        """9c Tc on 8h Qd 2s → gutshot, 4 outs."""
        hero = ["9c", "Tc"]
        board = ["8h", "Qd", "2s"]

        draw = classify_draw(hero, board)
        outs = count_outs(hero, board)

        assert draw == DrawType.GUTSHOT
        assert outs == 4

    def test_wheel_draw(self):
        """A2 on 3-4-K → gutshot (wheel draw is one-ended)."""
        hero = ["Ah", "2c"]
        board = ["3d", "4s", "Kh"]

        draw = classify_draw(hero, board)
        # Wheel draws (A-2-3-4) only complete one way with 5
        assert draw == DrawType.GUTSHOT


class TestComboDraw:
    """Test combo draw detection."""

    def test_combo_draw(self):
        """Flush draw + straight draw = combo draw."""
        hero = ["9h", "Th"]
        board = ["8h", "Jh", "2s"]

        draw = classify_draw(hero, board)
        outs = count_outs(hero, board)

        assert draw == DrawType.COMBO_DRAW
        # Flush (9) + OESD (8) - overlap (2) = 15
        assert outs == 15


class TestBackdoorFlush:
    """Test backdoor flush detection."""

    def test_backdoor_flush_on_flop(self):
        """3 to a flush on flop = backdoor flush."""
        hero = ["Ah", "Kh"]
        board = ["2h", "7c", "Qs"]

        draw = classify_draw(hero, board)
        assert draw == DrawType.BACKDOOR_FLUSH

    def test_no_backdoor_on_turn(self):
        """Backdoor flush not applicable on turn."""
        hero = ["Ah", "Kh"]
        board = ["2h", "7c", "Qs", "3d"]

        draw = classify_draw(hero, board)
        assert draw == DrawType.NONE


class TestRiverNoDraws:
    """Test that river has no draws."""

    def test_river_no_outs(self):
        """No outs on river."""
        hero = ["Ah", "Kh"]
        board = ["2h", "7h", "Qs", "3d", "8c"]

        outs = count_outs(hero, board)
        draw = classify_draw(hero, board)

        assert outs == 0
        assert draw == DrawType.NONE


class TestMadeHandDescription:
    """Test made hand descriptions."""

    def test_preflop_pocket_pair(self):
        """Pocket pair preflop."""
        result = made_hand_description(["Ah", "As"], [])
        assert "Pocket" in result
        assert "A" in result

    def test_preflop_suited(self):
        """Suited cards preflop."""
        result = made_hand_description(["Ah", "Kh"], [])
        assert "suited" in result

    def test_top_pair(self):
        """Top pair on flop."""
        result = made_hand_description(["Ah", "Kd"], ["Ac", "7h", "2s"])
        assert "Pair" in result or "Top" in result

    def test_flush_draw_with_pair(self):
        """Flush draw + made hand description."""
        result = made_hand_description(["Ah", "Kh"], ["2h", "7h", "Ac"])
        assert "Flush Draw" in result

    def test_two_pair(self):
        """Two pair description."""
        result = made_hand_description(["Ah", "7d"], ["Ac", "7h", "2s"])
        assert "Two Pair" in result

    def test_trips(self):
        """Three of a kind description."""
        result = made_hand_description(["7h", "7d"], ["7c", "Ah", "2s"])
        assert "Three" in result

    def test_straight(self):
        """Straight description."""
        result = made_hand_description(["9h", "Td"], ["8c", "Jh", "Qs"])
        assert "Straight" in result

    def test_flush(self):
        """Flush description."""
        result = made_hand_description(["Ah", "Kh"], ["2h", "7h", "Qh"])
        assert "Flush" in result
