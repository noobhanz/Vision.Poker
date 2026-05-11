#!/usr/bin/env python3
"""
Extract rank/suit templates from annotated screenshot fixtures.

Usage:
    python -m tools.extract_templates \
        --input tests/fixtures/sample_frames/pokerstars \
        --skin pokerstars_mac_cash \
        --output vision/templates
"""

import argparse
import json
from pathlib import Path
from typing import Iterable

import cv2

from vision.roi_config import ROIConfig, ROIRegion, load_skin_config


def _load_expected(frame_path: Path) -> dict | None:
    json_path = frame_path.with_suffix(".json")
    if not json_path.exists():
        return None
    with open(json_path) as f:
        return json.load(f)


def _cards_for_frame(expected: dict, roi_config: ROIConfig) -> Iterable[tuple[str, ROIRegion]]:
    hero_rois = roi_config.get_hero_card_rois()
    for card, roi in zip(expected.get("hero_cards", []), hero_rois):
        yield card, roi

    board_rois = roi_config.get_board_card_rois()
    for card, roi in zip(expected.get("board_cards", []), board_rois):
        yield card, roi


def _preprocess_template(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)
    _, thresholded = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY | cv2.THRESH_OTSU,
    )
    return thresholded


def _extract_rank_suit(card_crop):
    h, w = card_crop.shape[:2]

    rank = card_crop[
        int(h * 0.04) : int(h * 0.30),
        int(w * 0.04) : int(w * 0.38),
    ]
    suit = card_crop[
        int(h * 0.24) : int(h * 0.52),
        int(w * 0.04) : int(w * 0.38),
    ]

    return _preprocess_template(rank), _preprocess_template(suit)


def _normalize_card_template(card_crop):
    return cv2.resize(card_crop, (62, 84), interpolation=cv2.INTER_AREA)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract rank/suit templates")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Directory containing annotated fixture screenshots",
    )
    parser.add_argument(
        "--skin",
        "-s",
        default="pokerstars_mac_cash",
        help="Skin configuration to use",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="vision/templates",
        help="Template output directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing templates for labels already extracted",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    rank_dir = output_dir / "ranks"
    suit_dir = output_dir / "suits"
    card_dir = output_dir / "cards"
    rank_dir.mkdir(parents=True, exist_ok=True)
    suit_dir.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)

    roi_config = load_skin_config(args.skin)
    extracted_ranks = set()
    extracted_suits = set()

    for frame_path in sorted(input_dir.glob("*.png")):
        expected = _load_expected(frame_path)
        if not expected:
            continue

        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        height, width = frame.shape[:2]
        scaled_config = roi_config.scale_to_window(width, height)

        for slot_index, (card, roi) in enumerate(_cards_for_frame(expected, scaled_config)):
            if len(card) != 2:
                continue

            rank_label = card[0].upper()
            suit_label = card[1].lower()
            x, y, w, h = roi.as_tuple()
            crop = frame[y : y + h, x : x + w]
            if crop.size == 0:
                continue

            rank_template, suit_template = _extract_rank_suit(crop)
            card_template = _normalize_card_template(crop)
            card_path = output_dir / f"{rank_label}{suit_label}.png"
            variant_path = card_dir / f"{rank_label}{suit_label}_{frame_path.stem}_{slot_index}.png"
            rank_path = rank_dir / f"{rank_label}.png"
            suit_path = suit_dir / f"{suit_label}.png"

            if args.overwrite or not card_path.exists():
                cv2.imwrite(str(card_path), card_template)

            if args.overwrite or not variant_path.exists():
                cv2.imwrite(str(variant_path), card_template)

            if args.overwrite or not rank_path.exists():
                cv2.imwrite(str(rank_path), rank_template)
                extracted_ranks.add(rank_label)

            if args.overwrite or not suit_path.exists():
                cv2.imwrite(str(suit_path), suit_template)
                extracted_suits.add(suit_label)

    print(f"Rank templates written: {', '.join(sorted(extracted_ranks)) or 'none'}")
    print(f"Suit templates written: {', '.join(sorted(extracted_suits)) or 'none'}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
