"""
Compose card detections + OCR results into a validated GameState.
Infer current street from number of board cards detected.
Apply sanity checks: pot > 0, cards are valid, no duplicate cards.
Set overall confidence score based on individual detection confidences.
"""

from itertools import product
from typing import Optional

import numpy as np

from engine.models import GameState, Street
from .action_reader import ActionReader
from .card_detector import CardDetector, DetectedCard
from .ocr_engine import OCREngine
from .roi_config import ROIConfig


class StateParser:
    """
    Parse visual detections into a validated GameState.
    """

    def __init__(
        self,
        card_detector: Optional[CardDetector] = None,
        ocr_engine: Optional[OCREngine] = None,
    ):
        """
        Initialize state parser.

        Args:
            card_detector: CardDetector instance (creates default if None)
            ocr_engine: OCREngine instance (creates default if None)
        """
        self.card_detector = card_detector or CardDetector()
        self.ocr_engine = ocr_engine or OCREngine()
        self.action_reader = ActionReader(self.ocr_engine)
        self._last_parse_error = "OK"

    def _infer_street(self, num_board_cards: int) -> Street:
        """Infer the current street from board card count."""
        if num_board_cards == 0:
            return Street.PREFLOP
        elif num_board_cards == 3:
            return Street.FLOP
        elif num_board_cards == 4:
            return Street.TURN
        elif num_board_cards == 5:
            return Street.RIVER
        else:
            # Invalid state, default to flop if 1-2 cards visible
            return Street.FLOP if num_board_cards > 0 else Street.PREFLOP

    def _validate_cards(self, cards: list[str]) -> tuple[list[str], bool]:
        """
        Validate card list for duplicates and format.

        Returns:
            Tuple of (valid_cards, is_valid)
        """
        valid_ranks = set("23456789TJQKA")
        valid_suits = set("cdhs")

        seen = set()
        valid_cards = []

        for card in cards:
            if len(card) != 2:
                continue

            rank, suit = card[0].upper(), card[1].lower()

            if rank not in valid_ranks or suit not in valid_suits:
                continue

            normalized = rank + suit
            if normalized in seen:
                # Duplicate card - invalid state
                return valid_cards, False

            seen.add(normalized)
            valid_cards.append(normalized)

        return valid_cards, True

    def _calculate_confidence(
        self,
        hero_detections: list[DetectedCard],
        board_detections: list[DetectedCard],
        pot_value: Optional[float],
        bet_value: Optional[float],
    ) -> float:
        """
        Calculate overall confidence score.

        Weights:
        - Hero cards: 40% (must have both)
        - Board cards: 30% (varies by street)
        - Pot size: 15%
        - Bet amount: 15%
        """
        score = 0.0

        # Hero cards (40%)
        if len(hero_detections) == 2:
            hero_conf = sum(d.confidence for d in hero_detections) / 2
            score += 0.4 * hero_conf
        elif len(hero_detections) == 1:
            score += 0.2 * hero_detections[0].confidence

        # Board cards (30%)
        if board_detections:
            board_conf = sum(d.confidence for d in board_detections) / len(
                board_detections
            )
            score += 0.3 * board_conf
        else:
            # Preflop - no board cards is valid
            score += 0.3

        # Pot size (15%)
        if pot_value is not None and pot_value > 0:
            score += 0.15

        # Bet amount (15%)
        if bet_value is not None and bet_value >= 0:
            score += 0.15

        return min(score, 1.0)

    def _detect_unique_cards(
        self,
        frame: np.ndarray,
        rois,
        max_candidates_per_slot: int = 6,
        require_all_slots: bool = True,
    ) -> list[DetectedCard]:
        """
        Detect one card per fixed slot while avoiding duplicate card labels.

        Individual slot classifiers can be slightly wrong when chips overlap a
        card. Choosing the best non-duplicate assignment across slots lets the
        stronger slot claim the contested label and preserves the next-best
        candidate for the other slot.
        """
        candidates_by_slot: list[list[DetectedCard]] = []
        for roi in rois:
            candidates = self.card_detector.detect(frame, roi.as_tuple())
            candidates = sorted(
                candidates,
                key=lambda detection: detection.confidence,
                reverse=True,
            )[:max_candidates_per_slot]
            if candidates or require_all_slots:
                candidates_by_slot.append(candidates)

        if not candidates_by_slot:
            return []
        if any(not candidates for candidates in candidates_by_slot):
            if any(candidates for candidates in candidates_by_slot):
                self._last_parse_error = "INCOMPLETE_HERO_CARDS"
            return []

        best_assignment: tuple[DetectedCard, ...] | None = None
        best_score = -1.0
        for assignment in product(*candidates_by_slot):
            cards = [detection.card for detection in assignment]
            if len(set(cards)) != len(cards):
                continue

            score = sum(detection.confidence for detection in assignment)
            if score > best_score:
                best_assignment = assignment
                best_score = score

        if best_assignment is None and len(candidates_by_slot) > 1:
            self._last_parse_error = "DUPLICATE_CARDS"

        return list(best_assignment or [])

    def parse(
        self,
        frame: np.ndarray,
        roi_config: ROIConfig,
    ) -> Optional[GameState]:
        """
        Parse a frame into a GameState.

        Args:
            frame: Screenshot as np.ndarray (BGR)
            roi_config: ROI configuration for the current skin

        Returns:
            GameState if parsing succeeds, None if critical data missing
        """
        self._last_parse_error = "OK"

        # Detect hero cards
        hero_detections = self._detect_unique_cards(
            frame,
            roi_config.get_hero_card_rois(),
        )

        # Detect board cards
        board_detections = self._detect_unique_cards(
            frame,
            roi_config.get_board_card_rois(),
            require_all_slots=False,
        )

        # Extract text values
        pot_value: Optional[float] = None
        bet_value: Optional[float] = None
        hero_stack: Optional[float] = None
        villain_stacks: list[float] = []
        legal_actions: list[str] = []
        action_amounts: dict[str, float] = {}
        action_mode = "none"
        action_amount_unknown = False

        if roi_config.pot_size:
            pot_value = self.ocr_engine.read_number(
                frame, roi_config.pot_size.as_tuple()
            )

        if roi_config.bet_to_call:
            bet_value = self.ocr_engine.read_number(
                frame, roi_config.bet_to_call.as_tuple()
            )

        if roi_config.action_buttons:
            action_state = self.action_reader.read(
                frame,
                roi_config.action_buttons.as_tuple(),
            )
            legal_actions = action_state.legal_actions
            action_amounts = action_state.action_amounts
            action_mode = action_state.mode
            action_amount_unknown = action_state.amount_unknown
            if action_state.bet_to_call is not None:
                bet_value = action_state.bet_to_call

        if roi_config.hero_stack:
            hero_stack = self.ocr_engine.read_number(
                frame, roi_config.hero_stack.as_tuple()
            )

        for vs_roi in roi_config.villain_stacks:
            vs = self.ocr_engine.read_number(frame, vs_roi.as_tuple())
            if vs is not None:
                villain_stacks.append(vs)

        # Extract and validate cards
        hero_cards = [d.card for d in hero_detections]
        board_cards = [d.card for d in board_detections]

        hero_cards, hero_valid = self._validate_cards(hero_cards)
        board_cards, board_valid = self._validate_cards(board_cards)

        # Check for duplicates across hero and board
        all_cards = hero_cards + board_cards
        _, all_valid = self._validate_cards(all_cards)

        if not all_valid:
            # Duplicate cards detected - invalid state
            self._last_parse_error = "DUPLICATE_CARDS"
            return None

        # Must have at least hero cards to proceed
        if len(hero_cards) < 2:
            if self._last_parse_error == "OK":
                self._last_parse_error = (
                    "HERO_FOLDED" if not hero_cards else "INCOMPLETE_HERO_CARDS"
                )
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(
            hero_detections, board_detections, pot_value, bet_value
        )

        # Build GameState
        return GameState(
            hero_cards=hero_cards,
            board_cards=board_cards,
            pot_size=pot_value or 0.0,
            bet_to_call=bet_value or 0.0,
            hero_stack=hero_stack or 0.0,
            villain_stacks=villain_stacks,
            action_mode=action_mode,
            legal_actions=legal_actions,
            action_amounts=action_amounts,
            action_amount_unknown=action_amount_unknown,
            num_players=len(villain_stacks) + 1,
            street=self._infer_street(len(board_cards)),
            is_tournament=False,  # Could be detected from blind structure
            confidence=confidence,
        )

    def parse_with_fallback(
        self,
        frame: np.ndarray,
        roi_config: ROIConfig,
        min_confidence: float = 0.6,
    ) -> tuple[Optional[GameState], str]:
        """
        Parse with status message for UI feedback.

        Args:
            frame: Screenshot as np.ndarray
            roi_config: ROI configuration
            min_confidence: Minimum confidence to accept

        Returns:
            Tuple of (GameState or None, status message)
        """
        state = self.parse(frame, roi_config)

        if state is None:
            return None, self._last_parse_error

        if state.confidence < min_confidence:
            return state, "LOW_CONFIDENCE"

        if len(state.hero_cards) < 2:
            return state, "INCOMPLETE_HERO_CARDS"

        if state.pot_size <= 0:
            return state, "NO_POT_DETECTED"

        if state.action_amount_unknown:
            return state, "ACTION_AMOUNT_UNKNOWN"

        return state, "OK"
