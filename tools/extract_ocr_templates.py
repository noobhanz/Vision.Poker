#!/usr/bin/env python3
"""
Extract simple numeric OCR templates from annotated fixture screenshots.

This creates digit/dot templates for the lightweight OCR fallback.
"""

import argparse
import json
from pathlib import Path

import cv2

from vision.roi_config import load_skin_config


def _load_expected(frame_path: Path) -> dict | None:
    json_path = frame_path.with_suffix(".json")
    if not json_path.exists():
        return None
    with open(json_path) as f:
        return json.load(f)


def _format_amount(value: float) -> str:
    text = f"{value:.2f}"
    if text.endswith("00"):
        return str(int(round(value)))
    return text


def _preprocess(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
    scale = 4
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return mask


def _char_boxes(region):
    mask = _preprocess(region)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h < 8 or w < 2:
            continue
        boxes.append((x, y, w, h))
    return sorted(boxes), mask


def _save_chars(region, text: str, output_dir: Path, prefix: str) -> int:
    boxes, mask = _char_boxes(region)

    # Many poker labels include a leading dollar sign. Drop it when present.
    if len(boxes) == len(text) + 1:
        boxes = boxes[1:]

    if len(boxes) != len(text):
        return 0

    written = 0
    for idx, (char, box) in enumerate(zip(text, boxes)):
        if char not in "0123456789.":
            continue
        x, y, w, h = box
        pad = 3
        char_img = mask[
            max(0, y - pad) : min(mask.shape[0], y + h + pad),
            max(0, x - pad) : min(mask.shape[1], x + w + pad),
        ]
        label = "dot" if char == "." else char
        path = output_dir / f"{label}_{prefix}_{idx}.png"
        cv2.imwrite(str(path), char_img)
        written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract numeric OCR templates")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--output", "-o", default="vision/templates/ocr")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_skin_config(args.skin)

    total = 0
    for frame_path in sorted(input_dir.glob("*.png")):
        expected = _load_expected(frame_path)
        if not expected:
            continue

        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        height, width = frame.shape[:2]
        scaled = config.scale_to_window(width, height)

        if expected.get("pot_size", 0) > 0 and scaled.pot_size:
            x, y, w, h = scaled.pot_size.as_tuple()
            # Keep the right side of "Pot: $0.03", where the amount lives.
            region = frame[y : y + h, x + int(w * 0.45) : x + w]
            total += _save_chars(
                region,
                _format_amount(float(expected["pot_size"])),
                output_dir,
                f"{frame_path.stem}_pot",
            )

        if expected.get("hero_stack", 0) > 0 and scaled.hero_stack:
            x, y, w, h = scaled.hero_stack.as_tuple()
            region = frame[y : y + h, x : x + w]
            total += _save_chars(
                region,
                _format_amount(float(expected["hero_stack"])),
                output_dir,
                f"{frame_path.stem}_stack",
            )

    print(f"OCR templates written: {total}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
