import numpy as np

from capture.window_finder import WindowRect
from tools.live_screen_hud import CropMargins, crop_frame_for_live_read, format_metrics


def test_crop_frame_for_live_read_updates_frame_and_rect():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    rect = WindowRect(x=10, y=20, width=200, height=100, window_id=123, title="VLC")

    cropped, cropped_rect = crop_frame_for_live_read(
        frame,
        rect,
        CropMargins(left=5, top=7, right=11, bottom=13),
    )

    assert cropped.shape == (80, 184, 3)
    assert cropped_rect.x == 15
    assert cropped_rect.y == 27
    assert cropped_rect.width == 184
    assert cropped_rect.height == 80
    assert cropped_rect.window_id == 123
    assert cropped_rect.title == "VLC"


def test_crop_frame_for_live_read_clamps_oversized_margins():
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    rect = WindowRect(x=0, y=0, width=20, height=10)

    cropped, cropped_rect = crop_frame_for_live_read(
        frame,
        rect,
        CropMargins(left=50, top=50, right=50, bottom=50),
    )

    assert cropped.size == 0
    assert cropped_rect.width == 0
    assert cropped_rect.height == 0


def test_format_metrics_waiting_state():
    assert format_metrics(None) == "waiting_for_stability"
