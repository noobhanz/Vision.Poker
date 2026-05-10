#!/usr/bin/env python3
"""
Helper tool to annotate screenshots for building training data.

Usage:
    python -m tools.annotate --input raw_screenshots/ --output annotated/
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# Card labels
RANKS = "23456789TJQKA"
SUITS = ["c", "d", "h", "s"]  # clubs, diamonds, hearts, spades
SUIT_NAMES = {"c": "clubs", "d": "diamonds", "h": "hearts", "s": "spades"}


class CardAnnotator:
    """Interactive card annotation tool."""

    def __init__(self):
        self.annotations: list[dict] = []
        self.current_bbox: Optional[tuple[int, int, int, int]] = None
        self.drawing = False
        self.start_point: Optional[tuple[int, int]] = None

    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for drawing bounding boxes."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing and self.start_point:
                x1, y1 = self.start_point
                self.current_bbox = (
                    min(x1, x), min(y1, y),
                    abs(x - x1), abs(y - y1)
                )

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False

    def _draw_annotations(self, frame: np.ndarray) -> np.ndarray:
        """Draw all annotations on the frame."""
        display = frame.copy()

        # Draw existing annotations
        for ann in self.annotations:
            bbox = ann["bbox"]
            label = ann["label"]
            x, y, w, h = bbox

            # Color based on suit
            colors = {
                "c": (0, 128, 0),    # Green for clubs
                "d": (0, 0, 255),    # Red for diamonds
                "h": (0, 0, 255),    # Red for hearts
                "s": (128, 128, 128), # Gray for spades
            }
            suit = label[-1] if len(label) == 2 else "c"
            color = colors.get(suit, (255, 255, 0))

            cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
            cv2.putText(display, label, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Draw current bbox
        if self.current_bbox:
            x, y, w, h = self.current_bbox
            cv2.rectangle(display, (x, y), (x + w, y + h), (255, 0, 255), 2)

        return display

    def _get_card_label(self) -> Optional[str]:
        """Interactive prompt to get card label."""
        print("\nEnter card (e.g., 'Ah' for Ace of hearts):")
        print("Ranks: 2-9, T, J, Q, K, A")
        print("Suits: c(lubs), d(iamonds), h(earts), s(pades)")
        print("Press Enter to skip, 'u' to undo last")

        label = input("> ").strip()

        if label == "":
            return None
        if label.lower() == "u":
            return "UNDO"

        # Validate
        if len(label) == 2:
            rank = label[0].upper()
            suit = label[1].lower()
            if rank in RANKS and suit in SUITS:
                return rank + suit

        print("Invalid card format!")
        return None

    def annotate_image(self, image_path: Path) -> list[dict]:
        """Annotate a single image."""
        self.annotations = []
        self.current_bbox = None

        frame = cv2.imread(str(image_path))
        if frame is None:
            print(f"Failed to load: {image_path}")
            return []

        window_name = f"Annotate: {image_path.name} (press 'n' for next, 'q' to quit)"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self._mouse_callback)

        print(f"\nAnnotating: {image_path.name}")
        print("Draw bounding boxes around cards, then enter the card label.")
        print("Press 'n' to finish this image, 'q' to quit.")

        while True:
            display = self._draw_annotations(frame)
            cv2.imshow(window_name, display)

            key = cv2.waitKey(50) & 0xFF

            if key == ord("q"):
                cv2.destroyAllWindows()
                return []  # Signal to quit

            elif key == ord("n"):
                cv2.destroyAllWindows()
                return self.annotations

            elif key == 13 and self.current_bbox:  # Enter key
                label = self._get_card_label()

                if label == "UNDO" and self.annotations:
                    removed = self.annotations.pop()
                    print(f"Removed: {removed['label']}")
                elif label:
                    x, y, w, h = self.current_bbox
                    self.annotations.append({
                        "label": label,
                        "bbox": [x, y, w, h],
                    })
                    print(f"Added: {label} at ({x}, {y}, {w}, {h})")

                self.current_bbox = None

        cv2.destroyAllWindows()
        return self.annotations


def convert_to_yolo_format(
    annotations: list[dict],
    image_width: int,
    image_height: int,
) -> list[str]:
    """
    Convert annotations to YOLO format.

    YOLO format: class_id center_x center_y width height
    (all values normalized 0-1)
    """
    # Build class mapping
    all_cards = [r + s for r in RANKS for s in SUITS]
    class_map = {card: idx for idx, card in enumerate(all_cards)}

    lines = []
    for ann in annotations:
        label = ann["label"]
        bbox = ann["bbox"]
        x, y, w, h = bbox

        if label not in class_map:
            continue

        class_id = class_map[label]

        # Convert to YOLO format (center, normalized)
        center_x = (x + w / 2) / image_width
        center_y = (y + h / 2) / image_height
        norm_w = w / image_width
        norm_h = h / image_height

        lines.append(f"{class_id} {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}")

    return lines


def main():
    parser = argparse.ArgumentParser(description="Card Annotation Tool")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input directory with screenshots",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for annotations",
    )
    parser.add_argument(
        "--format",
        choices=["json", "yolo"],
        default="json",
        help="Output format",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find images
    image_files = sorted(
        list(input_dir.glob("*.png")) +
        list(input_dir.glob("*.jpg"))
    )

    if not image_files:
        print(f"No images found in {input_dir}")
        return

    print(f"Found {len(image_files)} images to annotate")

    annotator = CardAnnotator()
    all_annotations = {}

    for image_path in image_files:
        annotations = annotator.annotate_image(image_path)

        if annotations == []:
            # User pressed 'q' to quit
            break

        if annotations:
            all_annotations[image_path.name] = annotations

            # Load image to get dimensions
            img = cv2.imread(str(image_path))
            h, w = img.shape[:2]

            if args.format == "yolo":
                # Save YOLO format
                yolo_lines = convert_to_yolo_format(annotations, w, h)
                yolo_path = output_dir / f"{image_path.stem}.txt"
                with open(yolo_path, "w") as f:
                    f.write("\n".join(yolo_lines))
                print(f"Saved: {yolo_path}")
            else:
                # Save JSON format
                json_path = output_dir / f"{image_path.stem}.json"
                with open(json_path, "w") as f:
                    json.dump({
                        "image": image_path.name,
                        "width": w,
                        "height": h,
                        "annotations": annotations,
                    }, f, indent=2)
                print(f"Saved: {json_path}")

    # Save combined annotations
    if all_annotations:
        combined_path = output_dir / "all_annotations.json"
        with open(combined_path, "w") as f:
            json.dump(all_annotations, f, indent=2)
        print(f"\nSaved all annotations to: {combined_path}")

    print(f"\nAnnotated {len(all_annotations)} images")


if __name__ == "__main__":
    main()
