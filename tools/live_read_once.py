#!/usr/bin/env python3
"""Capture one poker table frame and print the parsed state.

Usage:
    python -m tools.live_read_once --title PokerStars --skin pokerstars_mac_cash
"""

import argparse
import json
import sys
from pathlib import Path

import cv2

from capture.screen import ScreenCapture
from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser

from .replay_test import (
    compute_metrics,
    draw_debug_overlay,
    metrics_to_dict,
    state_to_dict,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture and parse one live table frame")
    parser.add_argument(
        "--title",
        default="PokerStars",
        help="Poker window title or app-owner substring",
    )
    parser.add_argument(
        "--skin",
        default="pokerstars_mac_cash",
        help="Skin configuration to use",
    )
    parser.add_argument(
        "--mode",
        choices=["title", "active"],
        default="title",
        help="Window selection mode",
    )
    parser.add_argument(
        "--output-frame",
        default=None,
        help="Optional path to save the raw captured frame",
    )
    parser.add_argument(
        "--debug-output",
        default=None,
        help="Optional path to save an annotated debug frame",
    )
    parser.add_argument(
        "--monte-carlo",
        "-n",
        type=int,
        default=500,
        help="Number of Monte Carlo iterations",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )

    args = parser.parse_args()

    try:
        roi_config = load_skin_config(args.skin)
    except FileNotFoundError:
        print(f"Skin config not found: {args.skin}", file=sys.stderr)
        sys.exit(1)

    capture = ScreenCapture(title_substring=args.title, mode=args.mode)
    rect = capture.find_window()
    if rect is None:
        print(f"Poker window not found for title: {args.title}", file=sys.stderr)
        sys.exit(1)

    frame = capture.capture_rect(rect)
    if frame is None:
        print("Capture failed. Check macOS Screen Recording permission.", file=sys.stderr)
        sys.exit(1)

    if args.output_frame:
        output_frame = Path(args.output_frame)
        output_frame.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_frame), frame)

    scaled_config = roi_config.scale_to_window(rect.width, rect.height)
    parser_engine = StateParser(CardDetector(), OCREngine())
    state, status = parser_engine.parse_with_fallback(
        frame,
        scaled_config,
        min_confidence=0.5,
    )

    result = {
        "window": {
            "title": rect.title,
            "x": rect.x,
            "y": rect.y,
            "width": rect.width,
            "height": rect.height,
            "window_id": rect.window_id,
        },
        "status": status,
    }

    if state is not None:
        result["state"] = state_to_dict(state)
        metrics = compute_metrics(state, args.monte_carlo, status)
        result["metrics"] = metrics_to_dict(metrics)

        if args.debug_output:
            debug_output = Path(args.debug_output)
            debug_output.parent.mkdir(parents=True, exist_ok=True)
            debug = draw_debug_overlay(frame, state, metrics, scaled_config, status)
            cv2.imwrite(str(debug_output), debug)
            result["debug_output"] = str(debug_output)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Window: {rect.title or args.title} ({rect.width}x{rect.height})")
    print(f"Status: {status}")
    if state is None:
        sys.exit(1)

    print(f"Hero: {' '.join(state.hero_cards)}")
    print(f"Board: {' '.join(state.board_cards) if state.board_cards else '(preflop)'}")
    print(f"Street: {state.street.value}")
    print(f"Pot: ${state.pot_size:.2f}")
    print(f"Call: ${state.bet_to_call:.2f}")
    print(f"Action mode: {state.action_mode}")
    print(f"Legal actions: {', '.join(state.legal_actions) or '(none)'}")
    print(f"Action amounts: {state.action_amounts or '{}'}")
    if "metrics" in result:
        metrics = result["metrics"]
        print(f"Equity: {metrics['equity'] * 100:.1f}%")
        print(f"Recommendation: {metrics['recommendation']}")


if __name__ == "__main__":
    main()
