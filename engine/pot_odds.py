"""Pot odds and breakeven equity calculations."""


def pot_odds(pot_size: float, bet_to_call: float) -> float:
    """
    Calculate pot odds as the ratio of bet to call vs total pot after calling.

    Args:
        pot_size: Current pot size before calling
        bet_to_call: Amount hero must call

    Returns:
        Pot odds as a float between 0.0 and 1.0

    Formula: bet_to_call / (pot_size + bet_to_call)
    """
    if bet_to_call <= 0:
        return 0.0
    total_pot = pot_size + bet_to_call
    if total_pot <= 0:
        return 0.0
    return bet_to_call / total_pot


def required_equity(pot_size: float, bet_to_call: float) -> float:
    """
    Calculate the minimum equity needed to break even on a call.

    This is mathematically equivalent to pot odds - we need at least
    this much equity for a call to be +EV.

    Args:
        pot_size: Current pot size before calling
        bet_to_call: Amount hero must call

    Returns:
        Required equity as a float between 0.0 and 1.0
    """
    return pot_odds(pot_size, bet_to_call)


def is_call_profitable(equity: float, pot_size: float, bet_to_call: float) -> bool:
    """
    Determine if calling is profitable based on equity vs required equity.

    Args:
        equity: Hero's equity (0.0 to 1.0)
        pot_size: Current pot size
        bet_to_call: Amount to call

    Returns:
        True if equity >= required equity (call is +EV or breakeven)
    """
    return equity >= required_equity(pot_size, bet_to_call)
