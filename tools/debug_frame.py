#!/usr/bin/env python3
"""
Render an annotated debug image for one screenshot.

Usage:
    python -m tools.debug_frame --input frame.png --skin pokerstars --output debug.png
"""

import argparse
import sys
from pathlib import Path

import cv2

from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser

from .replay_test import compute_metrics, draw_debug_overlay


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Vision Poker debug frame")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Screenshot image to inspect",
    )
    parser.add_argument(
        "--skin",
        "-s",
        default="pokerstars",
        help="Skin configuration to use",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output image path. Defaults to debug_<input name>.png",
    )
    parser.add_argument(
        "--monte-carlo",
        "-n",
        type=int,
        default=1000,
        help="Number of Monte Carlo iterations",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    frame = cv2.imread(str(input_path))
    if frame is None:
        print(f"Failed to load image: {input_path}")
        sys.exit(1)

    try:
        roi_config = load_skin_config(args.skin)
    except FileNotFoundError:
        print(f"Skin config not found: {args.skin}")
        sys.exit(1)

    height, width = frame.shape[:2]
    scaled_config = roi_config.scale_to_window(width, height)

    state_parser = StateParser(CardDetector(), OCREngine())
    state, status = state_parser.parse_with_fallback(
        frame,
        scaled_config,
        min_confidence=0.5,
    )

    if state is None:
        print(f"Parse failed: {status}")
        sys.exit(1)

    try:
        metrics = compute_metrics(state, args.monte_carlo, status)
    except Exception as exc:
        print(f"Metrics failed: {exc}")
        sys.exit(1)

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"debug_{input_path.stem}.png")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    debug = draw_debug_overlay(frame, state, metrics, scaled_config, status)
    cv2.imwrite(str(output_path), debug)

    print(f"Saved debug image: {output_path}")
    print(f"Status: {status}")
    print(f"Hero: {' '.join(state.hero_cards)}")
    print(f"Board: {' '.join(state.board_cards) if state.board_cards else '(preflop)'}")
    print(f"Pot: {state.pot_size}  Call: {state.bet_to_call}")
    print(f"Recommendation: {metrics.recommendation}")


if __name__ == "__main__":
    main()
