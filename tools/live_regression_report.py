#!/usr/bin/env python3
"""Summarize live-readiness from an extracted frame sequence.

Usage:
    python -m tools.live_regression_report \
      --input /tmp/pokerstars_live_sequence_001 \
      --skin pokerstars_mac_cash \
      --stable-frames 2 \
      --output /tmp/live_regression_summary.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

from pipeline.stability import StateStabilizer
from tools.replay_test import compute_metrics, metrics_to_dict, state_to_dict
from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _frame_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [
        path
        for path in sorted(input_path.iterdir())
        if path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _load_manifest(input_path: Path) -> dict[str, Any] | None:
    manifest_path = (
        input_path / "video_manifest.json"
        if input_path.is_dir()
        else input_path.parent / "video_manifest.json"
    )
    if not manifest_path.exists():
        return None
    with manifest_path.open() as f:
        return json.load(f)


def _is_suspicious_money(state, max_reasonable_money: float) -> bool:
    money_values = [
        float(state.pot_size),
        float(state.bet_to_call),
        float(state.hero_stack),
        *[float(value) for value in state.villain_stacks],
        *[float(value) for value in state.action_amounts.values()],
    ]
    return any(value > max_reasonable_money for value in money_values)


def summarize_live_frames(
    input_path: Path,
    skin: str = "pokerstars_mac_cash",
    stable_frames: int = 2,
    monte_carlo_n: int = 20,
    max_reasonable_money: float = 10.0,
    sample_limit: int = 5,
) -> dict[str, Any]:
    """Run the parser over live frames and return a compact JSON summary."""
    frame_paths = _frame_paths(input_path)
    if not frame_paths:
        raise ValueError(f"No image files found in {input_path}")

    roi_config = load_skin_config(skin)
    state_parser = StateParser(CardDetector(), OCREngine())
    stabilizer = StateStabilizer(stable_frames)

    status_counts: Counter[str] = Counter()
    published_status_counts: Counter[str] = Counter()
    street_counts: Counter[str] = Counter()
    published_street_counts: Counter[str] = Counter()
    warning_samples: dict[str, list[dict[str, Any]]] = {}
    suspicious_published_ok: list[dict[str, Any]] = []

    active_frames = 0
    published_frames = 0
    actionable_ok_frames = 0
    published_warning_frames = 0

    for frame_path in frame_paths:
        frame = cv2.imread(str(frame_path))
        if frame is None:
            status_counts["FAILED_TO_LOAD"] += 1
            stabilizer.reset()
            continue

        scaled_config = roi_config.scale_to_window(frame.shape[1], frame.shape[0])
        state, status = state_parser.parse_with_fallback(
            frame,
            scaled_config,
            min_confidence=0.5,
        )

        status_counts[status] += 1
        if state is None:
            stabilizer.reset()
            if status != "NO_ACTIVE_HERO_CARDS":
                warning_samples.setdefault(status, []).append({"file": frame_path.name})
                warning_samples[status] = warning_samples[status][:sample_limit]
            continue

        active_frames += 1
        street_counts[state.street.value] += 1
        stability = stabilizer.observe(state, status)
        if not stability.is_stable:
            continue

        published_frames += 1
        published_status_counts[status] += 1
        published_street_counts[state.street.value] += 1

        metrics = compute_metrics(state, monte_carlo_n, status)
        if status == "OK":
            if metrics.action_mode == "decision":
                actionable_ok_frames += 1
            if _is_suspicious_money(state, max_reasonable_money):
                suspicious_published_ok.append(
                    {
                        "file": frame_path.name,
                        "state": state_to_dict(state),
                        "metrics": metrics_to_dict(metrics),
                    }
                )
        else:
            published_warning_frames += 1
            warning_samples.setdefault(status, []).append(
                {
                    "file": frame_path.name,
                    "hero_cards": state.hero_cards,
                    "board_cards": state.board_cards,
                    "street": state.street.value,
                    "pot_size": state.pot_size,
                    "hero_stack": state.hero_stack,
                }
            )
            warning_samples[status] = warning_samples[status][:sample_limit]

    total_frames = len(frame_paths)
    ok_frames = status_counts["OK"]
    published_ok_frames = published_status_counts["OK"]

    return {
        "input": str(input_path),
        "skin": skin,
        "stable_frames": stable_frames,
        "monte_carlo_n": monte_carlo_n,
        "max_reasonable_money": max_reasonable_money,
        "manifest": _load_manifest(input_path),
        "frames": {
            "total": total_frames,
            "active": active_frames,
            "ok": ok_frames,
            "warnings": total_frames - ok_frames - status_counts["NO_ACTIVE_HERO_CARDS"],
            "no_active_hero_cards": status_counts["NO_ACTIVE_HERO_CARDS"],
            "published": published_frames,
            "published_ok": published_ok_frames,
            "published_warnings": published_warning_frames,
            "actionable_published_ok": actionable_ok_frames,
        },
        "rates": {
            "active_rate": active_frames / total_frames if total_frames else 0.0,
            "ok_rate": ok_frames / total_frames if total_frames else 0.0,
            "published_ok_rate": published_ok_frames / total_frames if total_frames else 0.0,
            "published_warning_rate": (
                published_warning_frames / published_frames if published_frames else 0.0
            ),
        },
        "status_counts": dict(status_counts.most_common()),
        "published_status_counts": dict(published_status_counts.most_common()),
        "street_counts": dict(street_counts.most_common()),
        "published_street_counts": dict(published_street_counts.most_common()),
        "suspicious_published_ok_count": len(suspicious_published_ok),
        "suspicious_published_ok": suspicious_published_ok[:sample_limit],
        "warning_samples": warning_samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact live regression report")
    parser.add_argument("--input", "-i", required=True, help="Extracted frame directory")
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--stable-frames", type=int, default=2)
    parser.add_argument("--monte-carlo", "-n", type=int, default=20)
    parser.add_argument("--max-reasonable-money", type=float, default=10.0)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--output", "-o", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    try:
        report = summarize_live_frames(
            input_path=Path(args.input).expanduser(),
            skin=args.skin,
            stable_frames=args.stable_frames,
            monte_carlo_n=args.monte_carlo,
            max_reasonable_money=args.max_reasonable_money,
            sample_limit=args.sample_limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    output = json.dumps(report, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"Saved live regression report: {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
