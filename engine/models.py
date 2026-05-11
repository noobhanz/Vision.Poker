"""Data models for poker game state and computed metrics."""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class DrawType(Enum):
    NONE = "none"
    FLUSH_DRAW = "flush_draw"
    OESD = "open_ended_straight_draw"
    GUTSHOT = "gutshot"
    COMBO_DRAW = "combo_draw"
    BACKDOOR_FLUSH = "backdoor_flush"


@dataclass
class GameState:
    """Represents the current state of a poker hand as extracted from screen capture."""

    hero_cards: list[str]  # e.g. ["Ah", "Kd"]
    board_cards: list[str]  # e.g. ["2c", "7h", "Qs"]
    pot_size: float  # total pot in dollars/chips
    bet_to_call: float  # amount hero must call
    hero_stack: float
    villain_stacks: list[float] = field(default_factory=list)
    action_mode: str = "none"  # "decision" | "preselect" | "none"
    legal_actions: list[str] = field(default_factory=list)
    action_amounts: dict[str, float] = field(default_factory=dict)
    num_players: int = 2
    street: Street = Street.PREFLOP
    is_tournament: bool = False
    confidence: float = 0.0  # overall CV confidence score


@dataclass
class Metrics:
    """Computed poker metrics for display in the HUD."""

    equity: float  # 0.0–1.0
    pot_odds: float  # 0.0–1.0 (call / pot+call)
    required_equity: float  # pot_odds breakeven
    ev_call: float  # expected value of calling
    ev_fold: float  # always 0 (reference point)
    outs: int
    draw_type: DrawType
    made_hand_rank: str  # e.g. "Top Pair", "Flush"
    recommendation: str  # "FOLD" | "CALL" | "RAISE CANDIDATE"
    confidence: float  # pipeline confidence passthrough
    street: Street = Street.PREFLOP
    parse_status: str = "OK"
    action_mode: str = "none"
