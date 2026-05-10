#!/usr/bin/env python3
"""
Offline pipeline tester.

Loads a folder of saved frames (PNG screenshots) and runs the full pipeline
on each, printing extracted GameState + Metrics.

Usage:
    python -m tools.replay_test --input tests/fixtures/sample_frames/ --skin pokerstars
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config.settings import Settings
from engine.draws import classify_draw, count_outs, made_hand_description
from engine.equity import calculate_equity
from engine.ev import ev_call, ev_fold, recommendation
from engine.models import GameState, Metrics
from engine.pot_odds import pot_odds, required_equity
from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser


def compute_metrics(state: GameState, monte_carlo_n: int = 1000) -> Metrics:
    """Compute metrics from game state."""
    equity = calculate_equity(
        hero=state.hero_cards,
        board=state.board_cards,
        num_opponents=max(1, state.num_players - 1),
        n=monte_carlo_n,
    )

    po = pot_odds(state.pot_size, state.bet_to_call)
    req_eq = required_equity(state.pot_size, state.bet_to_call)
    ev = ev_call(equity, state.pot_size, state.bet_to_call)
    outs = count_outs(state.hero_cards, state.board_cards)
    draw_type = classify_draw(state.hero_cards, state.board_cards)
    made_hand = made_hand_description(state.hero_cards, state.board_cards)
    rec = recommendation(ev, equity, req_eq)

    return Metrics(
        equity=equity,
        pot_odds=po,
        required_equity=req_eq,
        ev_call=ev,
        ev_fold=ev_fold(),
        outs=outs,
        draw_type=draw_type,
        made_hand_rank=made_hand,
        recommendation=rec,
        confidence=state.confidence,
    )


def process_frame(
    frame_path: Path,
    state_parser: StateParser,
    roi_config,
    monte_carlo_n: int = 1000,
    debug_output_dir: Optional[Path] = None,
) -> tuple[Optional[GameState], Optional[Metrics], str]:
    """
    Process a single frame file.

    Returns:
        Tuple of (GameState, Metrics, status_message)
    """
    # Load frame
    frame = cv2.imread(str(frame_path))
    if frame is None:
        return None, None, f"Failed to load: {frame_path}"

    # Scale ROI config to frame size
    frame_height, frame_width = frame.shape[:2]
    scaled_config = roi_config.scale_to_window(frame_width, frame_height)

    # Parse state
    state, status = state_parser.parse_with_fallback(
        frame, scaled_config, min_confidence=0.5
    )

    if state is None:
        return None, None, f"Parse failed: {status}"

    # Compute metrics
    try:
        metrics = compute_metrics(state, monte_carlo_n)
    except Exception as e:
        return state, None, f"Metrics failed: {e}"

    # Save debug image if requested
    if debug_output_dir:
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        debug_frame = draw_debug_overlay(frame, state, metrics, scaled_config)
        debug_path = debug_output_dir / f"debug_{frame_path.stem}.png"
        cv2.imwrite(str(debug_path), debug_frame)

    return state, metrics, "OK"


def draw_debug_overlay(
    frame: np.ndarray,
    state: GameState,
    metrics: Metrics,
    roi_config,
) -> np.ndarray:
    """Draw debug information on the frame."""
    debug = frame.copy()

    # Draw ROI rectangles
    def draw_roi(roi, color, label):
        if roi:
            x, y, w, h = int(roi.x), int(roi.y), int(roi.w), int(roi.h)
            cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
            cv2.putText(debug, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # Hero cards
    for i, roi in enumerate(roi_config.get_hero_card_rois()):
        card = state.hero_cards[i] if i < len(state.hero_cards) else "?"
        draw_roi(roi, (0, 255, 0), f"Hero {card}")

    # Board cards
    for i, roi in enumerate(roi_config.get_board_card_rois()):
        card = state.board_cards[i] if i < len(state.board_cards) else ""
        if card:
            draw_roi(roi, (255, 0, 0), card)

    # Pot size
    draw_roi(roi_config.pot_size, (0, 255, 255), f"Pot: ${state.pot_size}")

    # Info overlay
    info_lines = [
        f"Hero: {' '.join(state.hero_cards)}",
        f"Board: {' '.join(state.board_cards) if state.board_cards else 'PREFLOP'}",
        f"Pot: ${state.pot_size:.0f}  Call: ${state.bet_to_call:.0f}",
        f"Equity: {metrics.equity*100:.1f}%",
        f"EV(call): ${metrics.ev_call:.2f}",
        f"Rec: {metrics.recommendation}",
        f"Conf: {metrics.confidence*100:.0f}%",
    ]

    y_offset = 30
    for line in info_lines:
        cv2.putText(debug, line, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(debug, line, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        y_offset += 25

    return debug


def main():
    parser = argparse.ArgumentParser(description="Replay Test Tool")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Directory containing frame images",
    )
    parser.add_argument(
        "--skin", "-s",
        default="pokerstars",
        help="Skin configuration to use",
    )
    parser.add_argument(
        "--debug-output", "-d",
        default=None,
        help="Directory to save annotated debug images",
    )
    parser.add_argument(
        "--monte-carlo", "-n",
        type=int,
        default=1000,
        help="Number of Monte Carlo iterations",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    debug_dir = Path(args.debug_output) if args.debug_output else None

    # Load skin config
    try:
        roi_config = load_skin_config(args.skin)
    except FileNotFoundError:
        print(f"Skin config not found: {args.skin}")
        sys.exit(1)

    # Initialize components
    card_detector = CardDetector()
    ocr_engine = OCREngine()
    state_parser = StateParser(card_detector, ocr_engine)

    # Find frame files
    frame_files = sorted(
        list(input_dir.glob("*.png")) +
        list(input_dir.glob("*.jpg")) +
        list(input_dir.glob("*.jpeg"))
    )

    if not frame_files:
        print(f"No image files found in {input_dir}")
        sys.exit(1)

    print(f"Processing {len(frame_files)} frames...")
    print()

    results = []

    for frame_path in frame_files:
        state, metrics, status = process_frame(
            frame_path,
            state_parser,
            roi_config,
            args.monte_carlo,
            debug_dir,
        )

        result = {
            "file": frame_path.name,
            "status": status,
        }

        if state:
            result["state"] = {
                "hero_cards": state.hero_cards,
                "board_cards": state.board_cards,
                "pot_size": state.pot_size,
                "bet_to_call": state.bet_to_call,
                "street": state.street.value,
                "confidence": state.confidence,
            }

        if metrics:
            result["metrics"] = {
                "equity": round(metrics.equity, 4),
                "pot_odds": round(metrics.pot_odds, 4),
                "ev_call": round(metrics.ev_call, 2),
                "outs": metrics.outs,
                "draw_type": metrics.draw_type.value,
                "made_hand": metrics.made_hand_rank,
                "recommendation": metrics.recommendation,
            }

        results.append(result)

        if not args.json:
            print(f"=== {frame_path.name} ===")
            print(f"Status: {status}")
            if state:
                print(f"Hero: {' '.join(state.hero_cards)}")
                print(f"Board: {' '.join(state.board_cards) if state.board_cards else '(preflop)'}")
                print(f"Pot: ${state.pot_size:.0f}  Call: ${state.bet_to_call:.0f}")
            if metrics:
                print(f"Equity: {metrics.equity*100:.1f}%")
                print(f"Pot Odds: {metrics.pot_odds*100:.1f}%")
                print(f"EV(call): ${metrics.ev_call:.2f}")
                print(f"Made Hand: {metrics.made_hand_rank}")
                print(f"Recommendation: {metrics.recommendation}")
            print()

    if args.json:
        print(json.dumps(results, indent=2))

    # Summary
    successful = sum(1 for r in results if r["status"] == "OK")
    print(f"Processed: {len(results)} frames")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")


if __name__ == "__main__":
    main()
