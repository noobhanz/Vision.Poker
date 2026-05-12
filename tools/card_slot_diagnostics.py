#!/usr/bin/env python3
"""Write per-card-slot diagnostics for screenshot fixtures.

Usage:
    python -m tools.card_slot_diagnostics \
      --input tests/fixtures/sample_frames/pokerstars \
      --skin pokerstars_mac_cash \
      --output /tmp/card_slot_diagnostics
"""

import argparse
import json
from pathlib import Path

import cv2

from vision.card_detector import CardDetector
from vision.roi_config import ROIRegion, load_skin_config


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _frame_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [
        path
        for path in sorted(input_path.iterdir())
        if path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _slot_rois(scaled_config) -> list[tuple[str, ROIRegion]]:
    slots = []
    for index, roi in enumerate(scaled_config.get_hero_card_rois(), start=1):
        slots.append((f"hero_card_{index}", roi))
    for index, roi in enumerate(scaled_config.get_board_card_rois(), start=1):
        slots.append((f"board_card_{index}", roi))
    return slots


def _save_crop(frame, roi: ROIRegion, output_path: Path) -> bool:
    x, y, w, h = roi.as_tuple()
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return False
    if x + w > frame.shape[1] or y + h > frame.shape[0]:
        return False
    crop = frame[y : y + h, x : x + w]
    if crop.size == 0:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), crop))


def diagnose_frame(
    frame_path: Path,
    detector: CardDetector,
    skin: str,
    output_dir: Path,
    threshold: float,
    top_n: int,
) -> dict:
    frame = cv2.imread(str(frame_path))
    if frame is None:
        return {
            "file": str(frame_path),
            "status": "FAILED_TO_LOAD",
            "slots": [],
        }

    config = load_skin_config(skin).scale_to_window(frame.shape[1], frame.shape[0])
    frame_output_dir = output_dir / frame_path.stem

    slots = []
    for slot_name, roi in _slot_rois(config):
        crop_path = frame_output_dir / f"{slot_name}.png"
        crop_written = _save_crop(frame, roi, crop_path)
        full_card = detector.full_card_template_diagnostics(
            frame,
            roi.as_tuple(),
            threshold=threshold,
            top_n=top_n,
        )
        rank_suit = detector.rank_suit_diagnostics(
            frame,
            roi.as_tuple(),
            threshold=threshold,
            top_n=top_n,
        )
        diagnostic = {
            "slot": slot_name,
            "roi": full_card["roi"],
            "crop_path": str(crop_path) if crop_written else None,
            "accepted": full_card["accepted"] or rank_suit["accepted"],
            "accepted_card": (
                full_card["accepted_card"]
                if full_card["accepted"]
                else rank_suit["accepted_card"]
            ),
            "confidence": (
                full_card["confidence"]
                if full_card["accepted"]
                else rank_suit["confidence"]
            ),
            "status": "ACCEPTED"
            if full_card["accepted"] or rank_suit["accepted"]
            else "LOW_CONFIDENCE",
            "full_card": full_card,
            "rank_suit": rank_suit,
        }
        slots.append(diagnostic)

    accepted_cards = [
        slot["accepted_card"]
        for slot in slots
        if slot.get("accepted") and slot.get("accepted_card")
    ]

    return {
        "file": str(frame_path),
        "image_size": {"width": int(frame.shape[1]), "height": int(frame.shape[0])},
        "skin": skin,
        "threshold": threshold,
        "status": "OK",
        "accepted_cards": accepted_cards,
        "slots": slots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Explain card recognition per ROI slot")
    parser.add_argument("--input", "-i", required=True, help="Image file or image directory")
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--output", "-o", default="debug/card_slot_diagnostics")
    parser.add_argument("--threshold", "-t", type=float, default=0.72)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    detector = CardDetector()
    reports = [
        diagnose_frame(
            frame_path,
            detector,
            args.skin,
            output_dir,
            args.threshold,
            args.top_n,
        )
        for frame_path in _frame_paths(input_path)
    ]

    report_path = output_dir / "card_slot_diagnostics.json"
    with report_path.open("w") as f:
        json.dump(reports, f, indent=2)

    if args.json:
        print(json.dumps(reports, indent=2))
        return

    print(f"Frames: {len(reports)}")
    print(f"Report: {report_path}")
    for report in reports:
        accepted = " ".join(report.get("accepted_cards", [])) or "(none)"
        print(f"{Path(report['file']).name}: {accepted}")


if __name__ == "__main__":
    main()
