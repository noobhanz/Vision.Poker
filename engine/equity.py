"""Monte Carlo equity calculation using phevaluator."""

import hashlib
import random
from typing import Optional

# Card utilities
RANKS = "23456789TJQKA"
SUITS = "cdhs"
ALL_CARDS = [r + s for r in RANKS for s in SUITS]


def parse_card(card: str) -> tuple[int, str]:
    """Parse card string like 'Ah' into (rank_index, suit)."""
    rank = card[0].upper()
    suit = card[1].lower()
    return RANKS.index(rank), suit


def remaining_deck(known_cards: list[str]) -> list[str]:
    """
    Return all cards not in the known cards list.

    Args:
        known_cards: List of card strings (e.g., ["Ah", "Kd"])

    Returns:
        List of remaining cards in the deck
    """
    known_normalized = {c[0].upper() + c[1].lower() for c in known_cards}
    return [c for c in ALL_CARDS if c not in known_normalized]


def _evaluate_hand_phevaluator(cards: list[str]) -> int:
    """
    Evaluate a 5-7 card hand using phevaluator.
    Lower score = better hand.
    """
    try:
        from phevaluator import evaluate_cards
        return evaluate_cards(*cards)
    except ImportError:
        # Fallback to basic evaluation if phevaluator not installed
        return _basic_evaluate(cards)


def _basic_evaluate(cards: list[str]) -> int:
    """
    Basic hand evaluation fallback when phevaluator is not available.
    Returns a score where lower is better.
    """
    # Parse cards
    parsed = [(RANKS.index(c[0].upper()), c[1].lower()) for c in cards]
    ranks = sorted([p[0] for p in parsed], reverse=True)
    suits = [p[1] for p in parsed]

    # Count ranks and suits
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1

    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    counts = sorted(rank_counts.values(), reverse=True)
    is_flush = max(suit_counts.values()) >= 5

    # Check for straight
    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0

    # Add ace low for wheel straight
    if 12 in unique_ranks:  # Ace
        unique_ranks_with_low_ace = unique_ranks + [-1]
    else:
        unique_ranks_with_low_ace = unique_ranks

    for i in range(len(unique_ranks_with_low_ace) - 4):
        window = unique_ranks_with_low_ace[i:i+5]
        if window[0] - window[4] == 4:
            is_straight = True
            straight_high = window[0]
            break

    # Hand rankings (lower = better)
    # Straight flush
    if is_flush and is_straight:
        return 1000 - straight_high

    # Four of a kind
    if counts[0] == 4:
        return 2000 - max(r for r, c in rank_counts.items() if c == 4) * 13

    # Full house
    if counts[0] == 3 and counts[1] >= 2:
        trips = max(r for r, c in rank_counts.items() if c == 3)
        pair = max(r for r, c in rank_counts.items() if c >= 2 and r != trips)
        return 3000 - trips * 13 - pair

    # Flush
    if is_flush:
        return 4000 - ranks[0]

    # Straight
    if is_straight:
        return 5000 - straight_high

    # Three of a kind
    if counts[0] == 3:
        return 6000 - max(r for r, c in rank_counts.items() if c == 3) * 13

    # Two pair
    if counts[0] == 2 and counts[1] == 2:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        return 7000 - pairs[0] * 13 - pairs[1]

    # One pair
    if counts[0] == 2:
        return 8000 - max(r for r, c in rank_counts.items() if c == 2) * 13

    # High card
    return 9000 - ranks[0]


def _run_simulation(
    hero: list[str],
    board: list[str],
    deck: list[str],
    num_opponents: int,
    rng: random.Random,
) -> float:
    """Run a single Monte Carlo simulation."""
    # Make a copy of deck and shuffle
    remaining = deck.copy()
    rng.shuffle(remaining)

    # Deal villain hands
    villain_hands = []
    idx = 0
    for _ in range(num_opponents):
        villain_hands.append([remaining[idx], remaining[idx + 1]])
        idx += 2

    # Complete the board if needed
    cards_needed = 5 - len(board)
    runout = remaining[idx:idx + cards_needed]
    full_board = board + runout

    # Evaluate hero hand
    hero_hand = hero + full_board
    hero_score = _evaluate_hand_phevaluator(hero_hand)

    # Evaluate villain hands
    hero_wins = True
    hero_ties = 0
    for v_hand in villain_hands:
        v_score = _evaluate_hand_phevaluator(v_hand + full_board)
        if v_score < hero_score:  # Lower is better
            hero_wins = False
            break
        elif v_score == hero_score:
            hero_ties += 1

    if not hero_wins:
        return 0.0
    elif hero_ties > 0:
        return 1.0 / (1 + hero_ties)  # Split pot
    else:
        return 1.0


def calculate_equity(
    hero: list[str],
    board: list[str],
    num_opponents: int = 1,
    n: int = 5000,
    seed: Optional[int] = None,
) -> float:
    """
    Calculate hero's equity using Monte Carlo simulation.

    Args:
        hero: Hero's hole cards, e.g., ["Ah", "Kd"]
        board: Community cards, e.g., ["2c", "7h", "Qs"]
        num_opponents: Number of opponents (default 1)
        n: Number of Monte Carlo iterations (default 5000)
        seed: Optional deterministic seed. If omitted, one is derived from the state.

    Returns:
        Equity as a float between 0.0 and 1.0

    Must complete in <100ms for 5000 iterations.
    """
    if len(hero) != 2:
        raise ValueError("Hero must have exactly 2 cards")
    if len(board) > 5:
        raise ValueError("Board cannot have more than 5 cards")

    # Normalize card format
    hero = [c[0].upper() + c[1].lower() for c in hero]
    board = [c[0].upper() + c[1].lower() for c in board]

    # Get remaining deck
    known = hero + board
    deck = remaining_deck(known)

    # Need at least 2 cards per opponent plus cards to complete board
    cards_needed = num_opponents * 2 + (5 - len(board))
    if len(deck) < cards_needed:
        raise ValueError("Not enough cards in deck for simulation")

    if seed is None:
        seed_key = "|".join(hero + board + [str(num_opponents), str(n)])
        seed = int.from_bytes(
            hashlib.blake2b(seed_key.encode("utf-8"), digest_size=8).digest(),
            "big",
        )
    rng = random.Random(seed)

    # Run simulations
    total_equity = 0.0
    for _ in range(n):
        total_equity += _run_simulation(hero, board, deck, num_opponents, rng)

    return total_equity / n
