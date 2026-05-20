"""Consecutive-state stabilization for live and replay pipelines."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class StabilityResult:
    """Result of one observed parse state."""

    key: tuple
    count: int
    required: int

    @property
    def is_stable(self) -> bool:
        return self.count >= self.required


class StateStabilizer:
    """Require repeated identical active parses before publishing metrics."""

    def __init__(self, stable_frames_required: int = 1):
        self.stable_frames_required = max(1, int(stable_frames_required))
        self._pending_key: Optional[tuple] = None
        self._pending_count = 0

    @property
    def pending_key(self) -> Optional[tuple]:
        return self._pending_key

    @property
    def pending_count(self) -> int:
        return self._pending_count

    def reset(self) -> None:
        """Clear active-hand stability tracking."""
        self._pending_key = None
        self._pending_count = 0

    def key_from_state(self, state, parse_status: str) -> tuple:
        """Return the parts of state that should be stable before updates."""
        return (
            tuple(state.hero_cards),
            tuple(state.board_cards),
            round(float(state.pot_size), 2),
            round(float(state.bet_to_call), 2),
            state.action_mode,
            tuple(state.legal_actions),
            parse_status,
        )

    def observe(self, state, parse_status: str) -> StabilityResult:
        """Track one parsed state and return its consecutive repeat count."""
        key = self.key_from_state(state, parse_status)
        if key == self._pending_key:
            self._pending_count += 1
        else:
            self._pending_key = key
            self._pending_count = 1

        return StabilityResult(
            key=key,
            count=self._pending_count,
            required=self.stable_frames_required,
        )
