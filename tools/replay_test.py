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

from engine.draws import classify_draw, count_outs, made_hand_description
from engine.equity import calculate_equity
from engine.ev import ev_call, ev_fold, recommendation
from engine.models import GameState, Metrics
from engine.pot_odds import pot_odds, required_equity
from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser


def compute_metrics(
    state: GameState,
    monte_carlo_n: int = 1000,
    parse_status: str = "OK",
) -> Metrics:
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
    rec = (
        recommendation(ev, equity, req_eq)
        if state.action_mode == "decision" and parse_status == "OK"
        else "WAIT"
    )

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
        street=state.street,
        parse_status=parse_status,
        action_mode=state.action_mode,
    )


def state_to_dict(state: GameState) -> dict:
    """Convert GameState to a stable JSON-serializable dict."""
    return {
        "hero_cards": state.hero_cards,
        "board_cards": state.board_cards,
        "pot_size": state.pot_size,
        "bet_to_call": state.bet_to_call,
        "hero_stack": state.hero_stack,
        "villain_stacks": state.villain_stacks,
        "action_mode": state.action_mode,
        "legal_actions": state.legal_actions,
        "action_amounts": state.action_amounts,
        "action_amount_unknown": state.action_amount_unknown,
        "num_players": state.num_players,
        "street": state.street.value,
        "confidence": state.confidence,
    }


def metrics_to_dict(metrics: Metrics) -> dict:
    """Convert Metrics to a stable JSON-serializable dict."""
    return {
        "equity": round(metrics.equity, 4),
        "pot_odds": round(metrics.pot_odds, 4),
        "required_equity": round(metrics.required_equity, 4),
        "ev_call": round(metrics.ev_call, 2),
        "outs": metrics.outs,
        "draw_type": metrics.draw_type.value,
        "made_hand": metrics.made_hand_rank,
        "recommendation": metrics.recommendation,
        "confidence": round(metrics.confidence, 4),
        "street": metrics.street.value,
        "parse_status": metrics.parse_status,
        "action_mode": metrics.action_mode,
    }


def load_expected(frame_path: Path) -> Optional[dict]:
    """
    Load expected state from a sidecar JSON file.

    Supported names:
    - frame.png -> frame.json
    - frame.png -> frame.expected.json
    """
    candidates = [
        frame_path.with_suffix(".json"),
        frame_path.with_suffix(".expected.json"),
    ]

    for candidate in candidates:
        if candidate.exists():
            with open(candidate) as f:
                return json.load(f)

    return None


def compare_expected(actual: dict, expected: dict, money_tolerance: float = 0.01) -> dict:
    """Compare parsed state against expected fixture values."""
    mismatches = []
    checked_fields = []

    def expected_value(key: str):
        if key in expected:
            return expected[key]
        if "state" in expected and key in expected["state"]:
            return expected["state"][key]
        return None

    for key in ["hero_cards", "board_cards", "street", "action_mode", "legal_actions"]:
        expected_item = expected_value(key)
        if expected_item is not None and actual.get(key) != expected_item:
            checked_fields.append(key)
            mismatches.append({
                "field": key,
                "expected": expected_item,
                "actual": actual.get(key),
            })
        elif expected_item is not None:
            checked_fields.append(key)

    expected_amounts = expected_value("action_amounts")
    if expected_amounts is not None:
        actual_amounts = actual.get("action_amounts", {})
        for action, expected_amount in expected_amounts.items():
            field = f"action_amounts.{action}"
            checked_fields.append(field)
            actual_amount = actual_amounts.get(action)
            if actual_amount is None or abs(float(actual_amount) - float(expected_amount)) > money_tolerance:
                mismatches.append({
                    "field": field,
                    "expected": expected_amount,
                    "actual": actual_amount,
                })

    for key in ["pot_size", "bet_to_call", "hero_stack"]:
        expected_item = expected_value(key)
        if expected_item is None:
            continue
        checked_fields.append(key)
        actual_item = actual.get(key)
        if actual_item is None or abs(float(actual_item) - float(expected_item)) > money_tolerance:
            mismatches.append({
                "field": key,
                "expected": expected_item,
                "actual": actual_item,
            })

    return {
        "passed": not mismatches,
        "mismatches": mismatches,
        "checked_fields": checked_fields,
    }


def summarize_expected_results(results: list[dict]) -> dict:
    """Summarize fixture comparison accuracy by expected field."""
    expected_results = [result for result in results if "expected" in result]
    summary = {
        "fixtures": {
            "total": len(expected_results),
            "passed": sum(
                1 for result in expected_results
                if result["expected"].get("passed", False)
            ),
        },
        "fields": {},
    }

    for result in expected_results:
        comparison = result["expected"]
        checked_fields = comparison.get("checked_fields", [])
        mismatched_fields = {
            mismatch["field"] for mismatch in comparison.get("mismatches", [])
        }

        if not checked_fields:
            checked_fields = sorted(mismatched_fields) or ["state"]

        for field in checked_fields:
            field_summary = summary["fields"].setdefault(
                field,
                {"passed": 0, "total": 0},
            )
            field_summary["total"] += 1
            if field not in mismatched_fields:
                field_summary["passed"] += 1

    for field_summary in summary["fields"].values():
        total = field_summary["total"]
        field_summary["accuracy"] = (
            field_summary["passed"] / total if total else 0.0
        )

    return summary


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
        metrics = compute_metrics(state, monte_carlo_n, status)
    except Exception as e:
        return state, None, f"Metrics failed: {e}"

    # Save debug image if requested
    if debug_output_dir:
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        debug_frame = draw_debug_overlay(frame, state, metrics, scaled_config, status)
        debug_path = debug_output_dir / f"debug_{frame_path.stem}.png"
        cv2.imwrite(str(debug_path), debug_frame)

    return state, metrics, status


def draw_debug_overlay(
    frame: np.ndarray,
    state: GameState,
    metrics: Metrics,
    roi_config,
    status: str = "OK",
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
    draw_roi(roi_config.bet_to_call, (255, 0, 255), f"Call: ${state.bet_to_call}")
    draw_roi(roi_config.hero_stack, (255, 255, 0), f"Stack: ${state.hero_stack}")

    for i, roi in enumerate(roi_config.villain_stacks):
        label = f"Villain {i + 1}"
        if i < len(state.villain_stacks):
            label += f": ${state.villain_stacks[i]}"
        draw_roi(roi, (128, 128, 255), label)

    # Info overlay
    info_lines = [
        f"Status: {status}",
        f"Hero: {' '.join(state.hero_cards)}",
        f"Board: {' '.join(state.board_cards) if state.board_cards else 'PREFLOP'}",
        f"Street: {state.street.value.upper()}",
        f"Pot: ${state.pot_size:.2f}  Call: ${state.bet_to_call:.2f}",
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
        help="Image file or directory containing frame images",
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any expected fixture comparison fails",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input path not found: {input_path}")
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
    if input_path.is_file():
        frame_files = [input_path]
    else:
        frame_files = sorted(
            list(input_path.glob("*.png")) +
            list(input_path.glob("*.jpg")) +
            list(input_path.glob("*.jpeg"))
        )

    if not frame_files:
        print(f"No image files found in {input_path}")
        sys.exit(1)

    if not args.json:
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

        expected = load_expected(frame_path)

        result = {
            "file": frame_path.name,
            "status": status,
        }

        if state:
            result["state"] = state_to_dict(state)

            if expected:
                result["expected"] = compare_expected(result["state"], expected)
        elif expected:
            result["expected"] = {
                "passed": False,
                "checked_fields": ["state"],
                "mismatches": [
                    {
                        "field": "state",
                        "expected": "parsed GameState",
                        "actual": status,
                    }
                ],
            }

        if metrics:
            result["metrics"] = metrics_to_dict(metrics)

        results.append(result)

        if not args.json:
            print(f"=== {frame_path.name} ===")
            print(f"Status: {status}")
            if state:
                print(f"Hero: {' '.join(state.hero_cards)}")
                print(f"Board: {' '.join(state.board_cards) if state.board_cards else '(preflop)'}")
                print(f"Pot: ${state.pot_size:.2f}  Call: ${state.bet_to_call:.2f}")
            if metrics:
                print(f"Equity: {metrics.equity*100:.1f}%")
                print(f"Pot Odds: {metrics.pot_odds*100:.1f}%")
                print(f"EV(call): ${metrics.ev_call:.2f}")
                print(f"Made Hand: {metrics.made_hand_rank}")
                print(f"Recommendation: {metrics.recommendation}")
            if expected:
                comparison = result.get("expected", {"passed": False, "mismatches": []})
                if comparison["passed"]:
                    print("Expected: PASS")
                else:
                    print("Expected: FAIL")
                    for mismatch in comparison["mismatches"]:
                        print(
                            f"  {mismatch['field']}: expected "
                            f"{mismatch['expected']!r}, got {mismatch['actual']!r}"
                        )
            print()

    if args.json:
        print(json.dumps(results, indent=2))

    accuracy_summary = summarize_expected_results(results)

    if args.strict:
        failures = [
            r for r in results
            if "expected" in r and not r["expected"]["passed"]
        ]
        if failures:
            sys.exit(1)

    if not args.json:
        # Summary
        successful = sum(
            1 for r in results
            if not r["status"].startswith("Parse failed")
            and not r["status"].startswith("Metrics failed")
            and not r["status"].startswith("Failed to load")
        )
        print(f"Processed: {len(results)} frames")
        print(f"Parsed: {successful}")
        print(f"Failed: {len(results) - successful}")

        annotated = accuracy_summary["fixtures"]["total"]
        passed = accuracy_summary["fixtures"]["passed"]
        reference_count = len(results) - annotated
        if annotated:
            print()
            print(f"Expected fixtures: {passed}/{annotated} passed")
            print(f"Reference-only frames: {reference_count}")
            print("Field accuracy:")
            for field, stats in sorted(accuracy_summary["fields"].items()):
                accuracy = stats["accuracy"] * 100
                print(
                    f"  {field}: {stats['passed']}/{stats['total']} "
                    f"({accuracy:.1f}%)"
                )


if __name__ == "__main__":
    main()
