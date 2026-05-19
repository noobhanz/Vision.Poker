#!/usr/bin/env python3
"""Fail/pass gate for live-readiness regression batches.

Usage:
    python -m tools.live_readiness_gate \
      --input tests/fixtures/live_sequences/pokerstars_live_smoke \
      --skin pokerstars_mac_cash \
      --stable-frames 2
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.live_regression_report import summarize_live_frames


def _parse_streets(value: str) -> set[str]:
    """Parse comma-separated required street names."""
    if not value.strip():
        return set()
    return {
        street.strip().lower()
        for street in value.split(",")
        if street.strip()
    }


def evaluate_live_readiness(
    report: dict[str, Any],
    *,
    max_suspicious_published_ok: int = 0,
    max_published_warning_rate: float = 0.05,
    min_published_ok: int = 1,
    min_actionable_published_ok: int = 0,
    required_published_streets: set[str] | None = None,
) -> dict[str, Any]:
    """Evaluate a live regression report against product-readiness thresholds."""
    required_published_streets = required_published_streets or set()
    failures: list[dict[str, Any]] = []

    frames = report.get("frames", {})
    rates = report.get("rates", {})
    published_street_counts = report.get("published_street_counts", {})

    suspicious_count = int(report.get("suspicious_published_ok_count", 0))
    if suspicious_count > max_suspicious_published_ok:
        failures.append(
            {
                "check": "suspicious_published_ok_count",
                "expected": f"<= {max_suspicious_published_ok}",
                "actual": suspicious_count,
            }
        )

    published_warning_rate = float(rates.get("published_warning_rate", 0.0))
    if published_warning_rate > max_published_warning_rate:
        failures.append(
            {
                "check": "published_warning_rate",
                "expected": f"<= {max_published_warning_rate}",
                "actual": published_warning_rate,
            }
        )

    published_ok = int(frames.get("published_ok", 0))
    if published_ok < min_published_ok:
        failures.append(
            {
                "check": "published_ok",
                "expected": f">= {min_published_ok}",
                "actual": published_ok,
            }
        )

    actionable_published_ok = int(frames.get("actionable_published_ok", 0))
    if actionable_published_ok < min_actionable_published_ok:
        failures.append(
            {
                "check": "actionable_published_ok",
                "expected": f">= {min_actionable_published_ok}",
                "actual": actionable_published_ok,
            }
        )

    missing_streets = sorted(
        street
        for street in required_published_streets
        if int(published_street_counts.get(street, 0)) <= 0
    )
    if missing_streets:
        failures.append(
            {
                "check": "required_published_streets",
                "expected": sorted(required_published_streets),
                "actual": sorted(published_street_counts),
                "missing": missing_streets,
            }
        )

    return {
        "passed": not failures,
        "failures": failures,
        "thresholds": {
            "max_suspicious_published_ok": max_suspicious_published_ok,
            "max_published_warning_rate": max_published_warning_rate,
            "min_published_ok": min_published_ok,
            "min_actionable_published_ok": min_actionable_published_ok,
            "required_published_streets": sorted(required_published_streets),
        },
        "summary": {
            "frames": frames,
            "rates": rates,
            "published_status_counts": report.get("published_status_counts", {}),
            "published_street_counts": published_street_counts,
            "suspicious_published_ok_count": suspicious_count,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate live-readiness regression output")
    parser.add_argument("--input", "-i", required=True, help="Extracted frame directory")
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--stable-frames", type=int, default=2)
    parser.add_argument("--monte-carlo", "-n", type=int, default=20)
    parser.add_argument("--max-reasonable-money", type=float, default=10.0)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--max-suspicious-published-ok", type=int, default=0)
    parser.add_argument("--max-published-warning-rate", type=float, default=0.05)
    parser.add_argument("--min-published-ok", type=int, default=1)
    parser.add_argument("--min-actionable-published-ok", type=int, default=0)
    parser.add_argument(
        "--required-published-streets",
        default="",
        help="Comma-separated street names that must appear in published states",
    )
    parser.add_argument("--output", "-o", default=None, help="Optional gate JSON path")
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

    gate = evaluate_live_readiness(
        report,
        max_suspicious_published_ok=args.max_suspicious_published_ok,
        max_published_warning_rate=args.max_published_warning_rate,
        min_published_ok=args.min_published_ok,
        min_actionable_published_ok=args.min_actionable_published_ok,
        required_published_streets=_parse_streets(args.required_published_streets),
    )
    output = json.dumps(gate, indent=2)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"Saved live readiness gate: {output_path}")
    else:
        print(output)

    sys.exit(0 if gate["passed"] else 1)


if __name__ == "__main__":
    main()
