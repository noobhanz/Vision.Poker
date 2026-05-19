from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mss")

from tools.replay_hud import (  # noqa: E402
    format_metrics_line,
    frame_paths_from_dir,
    iter_replay_frames,
    replay_rect_for_frame,
)


LIVE_SMOKE_DIR = Path("tests/fixtures/live_sequences/pokerstars_live_smoke")


def test_frame_paths_from_dir_returns_sorted_images():
    paths = frame_paths_from_dir(LIVE_SMOKE_DIR)

    assert len(paths) == 9
    assert paths == sorted(paths)
    assert paths[0].suffix == ".png"


def test_iter_replay_frames_samples_image_directory():
    frames = list(iter_replay_frames(LIVE_SMOKE_DIR, fps=2.0, max_frames=2))

    assert len(frames) == 2
    assert frames[0].index == 0
    assert frames[0].timestamp_seconds == 0.0
    assert frames[1].timestamp_seconds == 0.5
    assert frames[0].frame.shape[0] > 0
    assert frames[0].frame.shape[1] > 0


def test_replay_rect_matches_frame_dimensions():
    frame = np.zeros((688, 955, 3), dtype=np.uint8)

    rect = replay_rect_for_frame(frame, x=12, y=34)

    assert rect.x == 12
    assert rect.y == 34
    assert rect.width == 955
    assert rect.height == 688
    assert rect.title == "Vision Poker Replay"


def test_format_metrics_line_waiting_state():
    frame = next(iter_replay_frames(LIVE_SMOKE_DIR, fps=2.0, max_frames=1))

    line = format_metrics_line(frame, None)

    assert "000000" in line
    assert "waiting_for_stability" in line
