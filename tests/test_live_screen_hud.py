import numpy as np

from capture.window_finder import WindowRect
from pipeline.runner import PipelineRunner
from tools.live_screen_hud import (
    CropMargins,
    LiveScreenHudSession,
    crop_frame_for_live_read,
    format_metrics,
)
from vision.roi_config import ROIConfig, ROIRegion
from vision.table_locator import normalize_table_frame


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


def test_auto_table_locator_keeps_clean_table_fixture_full_size():
    import cv2

    frame = cv2.imread("tests/fixtures/sample_frames/pokerstars/pokerstars_large_002.png")
    assert frame is not None

    rect = WindowRect(x=0, y=0, width=frame.shape[1], height=frame.shape[0])
    normalized, normalized_rect, detected = normalize_table_frame(frame, rect)

    assert detected is not None
    assert normalized.shape == frame.shape
    assert normalized_rect.width == rect.width
    assert normalized_rect.height == rect.height


def test_live_session_skips_unchanged_relevant_regions():
    session = LiveScreenHudSession.__new__(LiveScreenHudSession)
    runner = PipelineRunner.__new__(PipelineRunner)
    runner.roi_config = ROIConfig(
        hero_card_1=ROIRegion(0.0, 0.0, 0.2, 0.2, is_relative=True)
    )
    runner._frame_buffer = None
    session.runner = runner

    rect = WindowRect(x=0, y=0, width=100, height=100, window_id=1, title="PokerStars")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    assert session._has_relevant_table_change(frame, rect) is True
    assert session._has_relevant_table_change(frame, rect) is False

    changed = frame.copy()
    changed[2:18, 2:8] = 255
    changed[2:8, 2:18] = 255
    assert session._has_relevant_table_change(changed, rect) is True
