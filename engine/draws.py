"""Outs counting and draw classification."""

from .models import DrawType

RANKS = "23456789TJQKA"
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}
SUITS = "cdhs"


def _parse_cards(cards: list[str]) -> list[tuple[int, str]]:
    """Parse card strings into (rank_value, suit) tuples."""
    return [(RANK_VALUES[c[0].upper()], c[1].lower()) for c in cards]


def _count_suit(cards: list[tuple[int, str]], suit: str) -> int:
    """Count cards of a specific suit."""
    return sum(1 for _, s in cards if s == suit)


def _get_ranks(cards: list[tuple[int, str]]) -> list[int]:
    """Get sorted list of unique ranks."""
    return sorted(set(r for r, _ in cards))


def _check_flush_draw(all_cards: list[tuple[int, str]]) -> tuple[bool, int]:
    """
    Check for flush draw.
    Returns (is_flush_draw, outs).
    """
    suit_counts = {}
    for _, s in all_cards:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    for suit, count in suit_counts.items():
        if count == 4:
            return True, 9  # 9 outs for flush draw
        if count == 5:
            return False, 0  # Already have flush, not a draw

    return False, 0


def _check_backdoor_flush(all_cards: list[tuple[int, str]]) -> bool:
    """Check for backdoor flush draw (3 to a flush on flop)."""
    suit_counts = {}
    for _, s in all_cards:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    return any(count == 3 for count in suit_counts.values())


def _check_straight_draw(ranks: list[int]) -> tuple[str, int]:
    """
    Check for straight draws.
    Returns (draw_type, outs).
    draw_type is 'oesd', 'gutshot', 'double_gutshot', or 'none'.
    """
    unique_ranks = sorted(set(ranks))

    # Add ace as low (value -1 for wheel)
    if 12 in unique_ranks:
        unique_ranks = [-1] + unique_ranks

    # Check for made straight first
    for i in range(len(unique_ranks) - 4):
        window = unique_ranks[i:i+5]
        if window[4] - window[0] == 4:
            return 'none', 0  # Already have straight

    # Check for 4 consecutive (OESD)
    for i in range(len(unique_ranks) - 3):
        window = unique_ranks[i:i+4]
        if window[3] - window[0] == 3:
            # Check if open-ended (can complete on both ends)
            low_end = window[0] - 1
            high_end = window[3] + 1

            # Can't be open-ended if one end is blocked
            if low_end < -1 or high_end > 12:
                # Only one end open (essentially a gutshot at the edge)
                return 'gutshot', 4
            return 'oesd', 8

    # Check for gutshot (4 cards with one gap)
    for i in range(len(unique_ranks) - 3):
        window = unique_ranks[i:i+4]
        gap = window[3] - window[0]
        if gap == 4:  # 4 cards spanning 5 values = 1 gap
            return 'gutshot', 4

    # Check for double gutshot (e.g., 5-7-8-9-J)
    for i in range(len(unique_ranks) - 4):
        window = unique_ranks[i:i+5]
        if window[4] - window[0] == 5:  # 5 cards spanning 6 values
            gaps = []
            for j in range(4):
                if window[j+1] - window[j] == 2:
                    gaps.append(window[j] + 1)
            if len(gaps) == 2:
                return 'double_gutshot', 8

    return 'none', 0


def count_outs(hero: list[str], board: list[str]) -> int:
    """
    Count the number of outs for improving hero's hand.

    Args:
        hero: Hero's hole cards
        board: Community cards

    Returns:
        Number of outs
    """
    if len(board) >= 5:
        return 0  # River, no more cards to come

    all_cards = _parse_cards(hero + board)

    # Count flush draw outs
    is_flush_draw, flush_outs = _check_flush_draw(all_cards)

    # Count straight draw outs
    ranks = [r for r, _ in all_cards]
    straight_type, straight_outs = _check_straight_draw(ranks)

    # Handle combo draw (deduplicate outs)
    if is_flush_draw and straight_outs > 0:
        # Overlap: typically 2 cards complete both draws
        # Flush draw suit cards that also complete straight
        return flush_outs + straight_outs - 2

    return max(flush_outs, straight_outs)


def classify_draw(hero: list[str], board: list[str]) -> DrawType:
    """
    Classify the type of draw hero has.

    Args:
        hero: Hero's hole cards
        board: Community cards

    Returns:
        DrawType enum value
    """
    if len(board) >= 5:
        return DrawType.NONE  # River, no draws

    all_cards = _parse_cards(hero + board)

    # Check for flush draw
    is_flush_draw, _ = _check_flush_draw(all_cards)

    # Check for straight draw
    ranks = [r for r, _ in all_cards]
    straight_type, _ = _check_straight_draw(ranks)

    # Combo draw
    if is_flush_draw and straight_type in ('oesd', 'gutshot', 'double_gutshot'):
        return DrawType.COMBO_DRAW

    # Flush draw
    if is_flush_draw:
        return DrawType.FLUSH_DRAW

    # Straight draws
    if straight_type == 'oesd':
        return DrawType.OESD
    if straight_type in ('gutshot', 'double_gutshot'):
        return DrawType.GUTSHOT

    # Check backdoor flush (only on flop)
    if len(board) == 3 and _check_backdoor_flush(all_cards):
        return DrawType.BACKDOOR_FLUSH

    return DrawType.NONE


def _evaluate_made_hand(cards: list[tuple[int, str]]) -> tuple[int, str, list[int]]:
    """
    Evaluate the made hand.
    Returns (hand_rank, hand_name, kickers).
    hand_rank: 1=high card, 2=pair, 3=two pair, 4=trips, 5=straight,
               6=flush, 7=full house, 8=quads, 9=straight flush
    """
    ranks = sorted([r for r, _ in cards], reverse=True)
    suits = [s for _, s in cards]

    # Count ranks
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1

    # Count suits
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    counts = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    is_flush = any(c >= 5 for c in suit_counts.values())

    # Check straight
    unique_ranks = sorted(set(ranks), reverse=True)
    if 12 in unique_ranks:
        unique_ranks_low = unique_ranks + [-1]
    else:
        unique_ranks_low = unique_ranks

    is_straight = False
    straight_high = 0
    for i in range(len(unique_ranks_low) - 4):
        window = unique_ranks_low[i:i+5]
        if window[0] - window[4] == 4:
            is_straight = True
            straight_high = window[0]
            break

    # Straight flush
    if is_flush and is_straight:
        high_name = RANKS[straight_high] if straight_high >= 0 else 'A'
        return 9, f"Straight Flush ({high_name} high)", [straight_high]

    # Quads
    if counts[0][1] == 4:
        quad_rank = counts[0][0]
        return 8, f"Four of a Kind ({RANKS[quad_rank]}s)", [quad_rank]

    # Full house
    if counts[0][1] == 3 and len(counts) > 1 and counts[1][1] >= 2:
        trips_rank = counts[0][0]
        pair_rank = counts[1][0]
        return 7, f"Full House ({RANKS[trips_rank]}s full of {RANKS[pair_rank]}s)", [trips_rank, pair_rank]

    # Flush
    if is_flush:
        flush_suit = max(suit_counts.items(), key=lambda x: x[1])[0]
        flush_cards = sorted([r for r, s in cards if s == flush_suit], reverse=True)
        return 6, f"Flush ({RANKS[flush_cards[0]]} high)", flush_cards[:5]

    # Straight
    if is_straight:
        high_name = RANKS[straight_high] if straight_high >= 0 else '5'  # Wheel
        return 5, f"Straight ({high_name} high)", [straight_high]

    # Trips
    if counts[0][1] == 3:
        trips_rank = counts[0][0]
        return 4, f"Three of a Kind ({RANKS[trips_rank]}s)", [trips_rank]

    # Two pair
    if counts[0][1] == 2 and len(counts) > 1 and counts[1][1] == 2:
        high_pair = counts[0][0]
        low_pair = counts[1][0]
        return 3, f"Two Pair ({RANKS[high_pair]}s and {RANKS[low_pair]}s)", [high_pair, low_pair]

    # One pair
    if counts[0][1] == 2:
        pair_rank = counts[0][0]
        kickers = sorted([r for r in ranks if r != pair_rank], reverse=True)
        # Determine pair quality
        if pair_rank == max(ranks):
            return 2, f"Top Pair ({RANKS[pair_rank]}s)", [pair_rank] + kickers[:3]
        elif pair_rank >= 10:  # T or higher
            return 2, f"Overpair ({RANKS[pair_rank]}s)", [pair_rank] + kickers[:3]
        else:
            return 2, f"Pair of {RANKS[pair_rank]}s", [pair_rank] + kickers[:3]

    # High card
    return 1, f"High Card ({RANKS[ranks[0]]})", ranks[:5]


def made_hand_description(hero: list[str], board: list[str]) -> str:
    """
    Return a human-readable description of the made hand.

    Args:
        hero: Hero's hole cards
        board: Community cards

    Returns:
        String like "Top Pair", "Flush Draw + Pair", etc.
    """
    if not board:
        # Preflop - describe hole cards
        parsed = _parse_cards(hero)
        r1, s1 = parsed[0]
        r2, s2 = parsed[1]

        if r1 == r2:
            return f"Pocket {RANKS[r1]}s"

        suited = "suited" if s1 == s2 else "offsuit"
        high = max(r1, r2)
        low = min(r1, r2)
        return f"{RANKS[high]}{RANKS[low]} {suited}"

    all_cards = _parse_cards(hero + board)
    _, hand_name, _ = _evaluate_made_hand(all_cards)

    # Add draw info if applicable
    draw = classify_draw(hero, board)
    if draw == DrawType.FLUSH_DRAW:
        return f"{hand_name} + Flush Draw"
    elif draw == DrawType.OESD:
        return f"{hand_name} + OESD"
    elif draw == DrawType.GUTSHOT:
        return f"{hand_name} + Gutshot"
    elif draw == DrawType.COMBO_DRAW:
        return f"{hand_name} + Combo Draw"

    return hand_name
