"""Expected Value calculations for poker decisions."""


def ev_call(equity: float, pot_size: float, bet_to_call: float) -> float:
    """
    Calculate the expected value of calling.

    Args:
        equity: Hero's equity (0.0 to 1.0)
        pot_size: Current pot size before calling
        bet_to_call: Amount hero must call

    Returns:
        Expected value of calling in chips/dollars

    Formula: EV(call) = (equity * pot_after_call) - ((1 - equity) * bet_to_call)

    Simplified: EV(call) = equity * (pot_size + bet_to_call) - bet_to_call
    """
    pot_after_call = pot_size + bet_to_call
    return equity * pot_after_call - bet_to_call


def ev_fold() -> float:
    """
    Calculate the expected value of folding.

    Returns:
        Always 0 - folding costs nothing additional (reference point)
    """
    return 0.0


def recommendation(ev_call_value: float, equity: float, req_equity: float) -> str:
    """
    Generate a recommendation based on EV and equity comparison.

    Args:
        ev_call_value: Expected value of calling
        equity: Hero's current equity
        req_equity: Required equity to break even

    Returns:
        "FOLD" - if EV is negative and equity is well below required
        "CALL" - if EV is positive
        "RAISE CANDIDATE" - if equity significantly exceeds required
    """
    equity_margin = equity - req_equity

    # Significant positive equity margin suggests raising might be better
    if equity_margin >= 0.15:  # 15+ percentage points above breakeven
        return "RAISE CANDIDATE"

    # Positive EV means calling is profitable
    if ev_call_value >= 0:
        return "CALL"

    # Negative EV and below required equity
    return "FOLD"
