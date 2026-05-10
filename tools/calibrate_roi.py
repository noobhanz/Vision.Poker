#!/usr/bin/env python3
"""
Interactive ROI calibration tool.

Usage:
    python -m tools.calibrate_roi --window "PokerStars" --output pokerstars.json

Controls:
    - Click and drag to draw ROI rectangles
    - Press 1-9 to assign region type to current selection
    - Press 's' to save configuration
    - Press 'c' to clear current selection
    - Press 'r' to reset all
    - Press 'q' to quit
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from capture.screen import ScreenCapture


# Region types and their keyboard shortcuts
REGION_TYPES = {
    "1": "hero_card_1",
    "2": "hero_card_2",
    "3": "board_card_1",
    "4": "board_card_2",
    "5": "board_card_3",
    "6": "board_card_4",
    "7": "board_card_5",
    "p": "pot_size",
    "b": "bet_to_call",
    "h": "hero_stack",
    "v": "villain_stack",
    "a": "action_buttons",
}


class ROICalibrator:
    """Interactive ROI calibration tool."""

    def __init__(self, window_title: str):
        self.window_title = window_title
        self.capture = ScreenCapture(window_title)

        self.frame: Optional[np.ndarray] = None
        self.regions: dict[str, dict] = {}
        self.villain_stacks: list[dict] = []

        # Drawing state
        self.drawing = False
        self.start_point: Optional[tuple[int, int]] = None
        self.current_rect: Optional[tuple[int, int, int, int]] = None

    def capture_frame(self) -> bool:
        """Capture a frame from the poker window."""
        self.frame = self.capture.capture()
        return self.frame is not None

    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for drawing rectangles."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.current_rect = None

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing and self.start_point:
                # Calculate rectangle
                x1, y1 = self.start_point
                self.current_rect = (
                    min(x1, x),
                    min(y1, y),
                    abs(x - x1),
                    abs(y - y1),
                )

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            if self.start_point:
                x1, y1 = self.start_point
                self.current_rect = (
                    min(x1, x),
                    min(y1, y),
                    abs(x - x1),
                    abs(y - y1),
                )

    def _draw_regions(self, frame: np.ndarray) -> np.ndarray:
        """Draw all defined regions on the frame."""
        display = frame.copy()

        # Colors for different region types
        colors = {
            "hero_card": (0, 255, 0),  # Green
            "board_card": (255, 0, 0),  # Blue
            "pot_size": (0, 255, 255),  # Yellow
            "bet_to_call": (255, 0, 255),  # Magenta
            "hero_stack": (255, 255, 0),  # Cyan
            "villain_stack": (128, 128, 255),  # Light red
            "action_buttons": (128, 255, 128),  # Light green
        }

        # Draw defined regions
        for name, roi in self.regions.items():
            # Determine color
            for key, color in colors.items():
                if key in name:
                    break
            else:
                color = (255, 255, 255)

            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                display, name, (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )

        # Draw villain stacks
        for i, roi in enumerate(self.villain_stacks):
            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (128, 128, 255), 2)
            cv2.putText(
                display, f"villain_stack_{i+1}", (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 255), 1
            )

        # Draw current selection
        if self.current_rect:
            x, y, w, h = self.current_rect
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 0, 255), 2)

        return display

    def _print_help(self):
        """Print help text."""
        print("\n=== ROI Calibration Tool ===")
        print("Controls:")
        print("  Click + drag : Draw ROI rectangle")
        print("  1-2         : Hero cards")
        print("  3-7         : Board cards (flop/turn/river)")
        print("  p           : Pot size")
        print("  b           : Bet to call")
        print("  h           : Hero stack")
        print("  v           : Add villain stack")
        print("  a           : Action buttons")
        print("  s           : Save configuration")
        print("  c           : Clear current selection")
        print("  r           : Reset all regions")
        print("  q           : Quit")
        print()

    def run(self, output_path: Path) -> None:
        """Run the calibration tool."""
        if not self.capture_frame():
            print(f"Could not find window: {self.window_title}")
            print("Make sure the poker client is open and visible.")
            return

        self._print_help()

        window_name = "ROI Calibration - Press 'q' to quit"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self._mouse_callback)

        frame_height, frame_width = self.frame.shape[:2]
        print(f"Frame size: {frame_width}x{frame_height}")

        while True:
            # Recapture periodically
            new_frame = self.capture.capture()
            if new_frame is not None:
                self.frame = new_frame

            # Draw UI
            display = self._draw_regions(self.frame)

            # Add instructions
            cv2.putText(
                display,
                "Draw rectangle, then press key to assign region type",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

            cv2.imshow(window_name, display)
            key = cv2.waitKey(50) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("s"):
                # Save configuration
                self._save_config(output_path, frame_width, frame_height)
                print(f"Saved configuration to {output_path}")

            elif key == ord("c"):
                # Clear current selection
                self.current_rect = None
                print("Selection cleared")

            elif key == ord("r"):
                # Reset all
                self.regions.clear()
                self.villain_stacks.clear()
                self.current_rect = None
                print("All regions reset")

            elif self.current_rect is not None:
                # Assign region
                key_char = chr(key)
                if key_char in REGION_TYPES:
                    region_name = REGION_TYPES[key_char]
                    x, y, w, h = self.current_rect

                    if region_name == "villain_stack":
                        self.villain_stacks.append({"x": x, "y": y, "w": w, "h": h})
                        print(f"Added villain_stack_{len(self.villain_stacks)}")
                    else:
                        self.regions[region_name] = {"x": x, "y": y, "w": w, "h": h}
                        print(f"Assigned {region_name}: ({x}, {y}, {w}, {h})")

                    self.current_rect = None

        cv2.destroyAllWindows()

    def _save_config(self, output_path: Path, width: int, height: int) -> None:
        """Save the configuration to JSON."""
        config = {
            "base_resolution": {"width": width, "height": height},
            **self.regions,
        }

        if self.villain_stacks:
            config["villain_stacks"] = self.villain_stacks

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="ROI Calibration Tool")
    parser.add_argument(
        "--window", "-w",
        required=True,
        help="Poker client window title",
    )
    parser.add_argument(
        "--output", "-o",
        default="custom_skin.json",
        help="Output filename (saved to config/skins/)",
    )

    args = parser.parse_args()

    output_path = Path(__file__).parent.parent / "config" / "skins" / args.output

    calibrator = ROICalibrator(args.window)
    calibrator.run(output_path)


if __name__ == "__main__":
    main()
