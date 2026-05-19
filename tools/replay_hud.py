#!/usr/bin/env python3
"""Replay saved table frames through the real HUD pipeline.

This is a developer bridge between offline fixtures and live screen capture:
it feeds recorded pixels into ``PipelineRunner.process_frame`` so the parser,
stabilizer, metrics, and HUD all exercise the same path used by live mode.

Examples:
    python -m tools.replay_hud --input tests/fixtures/live_sequences/pokerstars_live_smoke
    python -m tools.replay_hud --input recording.mov --fps 2 --no-hud --max-frames 50
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np

from capture.window_finder import WindowRect
from config.settings import Settings
from engine.models import Metrics
from pipeline.runner import PipelineRunner


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass
class ReplayFrame:
    """One sampled replay frame."""

    frame: np.ndarray
    index: int
    timestamp_seconds: float
    source: str


def is_video_path(path: Path) -> bool:
    """Return whether a path looks like a supported video file."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


def frame_paths_from_dir(input_dir: Path) -> list[Path]:
    """Return sorted image paths from a replay directory."""
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def iter_image_frames(
    input_path: Path,
    *,
    fps: float,
    max_frames: Optional[int] = None,
) -> Iterator[ReplayFrame]:
    """Yield frames from a single image or an image directory."""
    paths = frame_paths_from_dir(input_path) if input_path.is_dir() else [input_path]
    interval = 1.0 / fps if fps > 0 else 0.0

    yielded = 0
    for index, path in enumerate(paths):
        if max_frames is not None and yielded >= max_frames:
            break
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        yield ReplayFrame(
            frame=frame,
            index=index,
            timestamp_seconds=index * interval,
            source=str(path),
        )
        yielded += 1


def iter_video_frames(
    input_path: Path,
    *,
    fps: float,
    max_frames: Optional[int] = None,
) -> Iterator[ReplayFrame]:
    """Yield sampled frames from a video file."""
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {input_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or fps or 1.0
    sample_every = max(1, round(source_fps / fps)) if fps > 0 else 1

    source_index = 0
    yielded = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if source_index % sample_every == 0:
                if max_frames is not None and yielded >= max_frames:
                    break
                yield ReplayFrame(
                    frame=frame,
                    index=source_index,
                    timestamp_seconds=source_index / source_fps,
                    source=str(input_path),
                )
                yielded += 1

            source_index += 1
    finally:
        capture.release()


def iter_replay_frames(
    input_path: Path,
    *,
    fps: float = 2.0,
    max_frames: Optional[int] = None,
) -> Iterator[ReplayFrame]:
    """Yield replay frames from an image, image directory, or video."""
    if input_path.is_dir() or input_path.suffix.lower() in IMAGE_EXTENSIONS:
        yield from iter_image_frames(input_path, fps=fps, max_frames=max_frames)
        return

    if is_video_path(input_path):
        yield from iter_video_frames(input_path, fps=fps, max_frames=max_frames)
        return

    raise ValueError(f"Unsupported replay input: {input_path}")


def replay_rect_for_frame(
    frame: np.ndarray,
    *,
    x: int = 80,
    y: int = 80,
    window_id: int = 0,
    title: str = "Vision Poker Replay",
) -> WindowRect:
    """Build a synthetic window rectangle matching a replay frame."""
    height, width = frame.shape[:2]
    return WindowRect(
        x=x,
        y=y,
        width=width,
        height=height,
        window_id=window_id,
        title=title,
    )


def build_runner(
    *,
    skin: str,
    stable_frames: int,
    monte_carlo: int,
    debug: bool,
) -> PipelineRunner:
    """Create a runner configured for replay instead of live capture."""
    settings = Settings(
        skin_config=skin,
        stable_frames_required=stable_frames,
        monte_carlo_n=monte_carlo,
        debug_mode=debug,
    )
    return PipelineRunner(settings)


async def process_replay_frame(
    runner: PipelineRunner,
    replay_frame: ReplayFrame,
    rect: WindowRect,
) -> Optional[Metrics]:
    """Process one replay frame through the normal live pipeline."""
    return await runner.process_frame(replay_frame.frame, rect)


def format_metrics_line(
    replay_frame: ReplayFrame,
    metrics: Optional[Metrics],
) -> str:
    """Return a compact console line for replay diagnostics."""
    prefix = f"{replay_frame.index:06d} {replay_frame.timestamp_seconds:7.2f}s"
    if metrics is None:
        return f"{prefix} waiting_for_stability"

    return (
        f"{prefix} {metrics.parse_status} {metrics.street.value} "
        f"equity={metrics.equity * 100:5.1f}% "
        f"pot_odds={metrics.pot_odds * 100:5.1f}% "
        f"ev={metrics.ev_call:6.2f} rec={metrics.recommendation} "
        f"mode={metrics.action_mode}"
    )


def run_console(args: argparse.Namespace) -> int:
    """Run replay without the HUD and print metric updates."""
    runner = build_runner(
        skin=args.skin,
        stable_frames=args.stable_frames,
        monte_carlo=args.monte_carlo,
        debug=args.debug,
    )

    frames = iter_replay_frames(
        args.input,
        fps=args.fps,
        max_frames=args.max_frames,
    )
    interval = (1.0 / args.fps / args.speed) if args.fps > 0 and args.speed > 0 else 0.0
    processed = 0
    published = 0

    for replay_frame in frames:
        rect = replay_rect_for_frame(
            replay_frame.frame,
            x=args.x,
            y=args.y,
        )
        metrics = asyncio.run(process_replay_frame(runner, replay_frame, rect))
        processed += 1
        if metrics is not None:
            published += 1
        print(format_metrics_line(replay_frame, metrics))
        if args.realtime and interval > 0:
            time.sleep(interval)

    print(f"processed={processed} published={published}")
    return 0 if processed else 1


def run_hud(args: argparse.Namespace) -> int:
    """Run replay while updating the real PyQt HUD."""
    from PyQt6.QtCore import QTimer
    from overlay.hud import create_hud_app

    frames = list(
        iter_replay_frames(
            args.input,
            fps=args.fps,
            max_frames=args.max_frames,
        )
    )
    if not frames:
        print(f"No replay frames found in: {args.input}", file=sys.stderr)
        return 1

    runner = build_runner(
        skin=args.skin,
        stable_frames=args.stable_frames,
        monte_carlo=args.monte_carlo,
        debug=args.debug,
    )

    app, hud = create_hud_app(
        hotkey=args.hotkey,
        opacity=args.opacity,
        position=args.position,
    )
    hud.show()
    hud.set_status("REPLAY")

    interval_ms = max(1, int(1000 / args.fps / args.speed)) if args.fps > 0 else 1
    state = {"index": 0}
    timer = QTimer()

    def tick() -> None:
        if state["index"] >= len(frames):
            if args.loop:
                state["index"] = 0
                runner._stabilizer.reset()
            else:
                timer.stop()
                app.quit()
                return

        replay_frame = frames[state["index"]]
        rect = replay_rect_for_frame(
            replay_frame.frame,
            x=args.x,
            y=args.y,
        )
        metrics = asyncio.run(process_replay_frame(runner, replay_frame, rect))
        hud.position_over_window(rect)
        if metrics is not None:
            hud.update_metrics(metrics)
        elif args.debug:
            print(format_metrics_line(replay_frame, metrics))
        state["index"] += 1

    timer.timeout.connect(tick)
    timer.start(interval_ms)
    tick()
    return app.exec()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay saved PokerStars frames through the live HUD pipeline",
    )
    parser.add_argument("--input", "-i", type=Path, required=True)
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--monte-carlo", "-n", type=int, default=500)
    parser.add_argument("--stable-frames", type=int, default=2)
    parser.add_argument("--no-hud", action="store_true")
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--x", type=int, default=80)
    parser.add_argument("--y", type=int, default=80)
    parser.add_argument("--hotkey", default="F9")
    parser.add_argument("--opacity", type=float, default=0.88)
    parser.add_argument(
        "--position",
        default="top-right",
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
    )

    args = parser.parse_args()
    if not args.input.exists():
        parser.error(f"Input does not exist: {args.input}")
    if args.fps <= 0:
        parser.error("--fps must be greater than 0")
    if args.speed <= 0:
        parser.error("--speed must be greater than 0")
    if args.stable_frames <= 0:
        parser.error("--stable-frames must be greater than 0")
    return args


def main() -> None:
    args = parse_args()
    code = run_console(args) if args.no_hud else run_hud(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
