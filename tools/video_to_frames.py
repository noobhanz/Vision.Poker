#!/usr/bin/env python3
"""Extract ordered replay frames from a screen recording.

Usage:
    python -m tools.video_to_frames \
      --input live_recording.mov \
      --output tests/fixtures/live_sequences/pokerstars_live_001 \
      --fps 2
"""

import argparse
import json
import sys
from pathlib import Path

import cv2


def extract_video_frames(
    input_path: Path,
    output_dir: Path,
    target_fps: float = 2.0,
    prefix: str = "frame",
    image_extension: str = "png",
    max_frames: int | None = None,
) -> dict:
    """Extract frames from a video at a fixed rate."""
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {input_path}")

    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if source_fps <= 0:
        raise ValueError("Could not determine source video FPS")

    output_dir.mkdir(parents=True, exist_ok=True)
    frame_interval = max(1, round(source_fps / target_fps))
    written = 0
    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % frame_interval == 0:
            timestamp_seconds = frame_index / source_fps
            output_path = output_dir / (
                f"{prefix}_{written + 1:05d}_{timestamp_seconds:08.2f}s."
                f"{image_extension}"
            )
            cv2.imwrite(str(output_path), frame)
            written += 1
            if max_frames is not None and written >= max_frames:
                break

        frame_index += 1

    cap.release()

    manifest = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "source_fps": source_fps,
        "source_frames": source_frames,
        "source_width": width,
        "source_height": height,
        "target_fps": target_fps,
        "frame_interval": frame_interval,
        "extracted_frames": written,
        "prefix": prefix,
        "image_extension": image_extension,
    }

    manifest_path = output_dir / "video_manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ordered replay frames from video")
    parser.add_argument("--input", "-i", required=True, help="Input video path")
    parser.add_argument("--output", "-o", required=True, help="Output frame directory")
    parser.add_argument("--fps", type=float, default=2.0, help="Extraction FPS")
    parser.add_argument("--prefix", default="frame", help="Output frame filename prefix")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    try:
        manifest = extract_video_frames(
            input_path=Path(args.input).expanduser(),
            output_dir=Path(args.output).expanduser(),
            target_fps=args.fps,
            prefix=args.prefix,
            max_frames=args.max_frames,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(f"Extracted: {manifest['extracted_frames']} frames")
    print(f"Source: {manifest['source_width']}x{manifest['source_height']} @ {manifest['source_fps']:.2f} fps")
    print(f"Output: {manifest['output_dir']}")


if __name__ == "__main__":
    main()
