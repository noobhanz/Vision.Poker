import pytest

pytest.importorskip("mss")

from pipeline.runner import PipelineRunner
from vision.roi_config import ROIConfig, ROIRegion


def test_frame_buffer_tracks_action_and_amount_regions():
    runner = PipelineRunner.__new__(PipelineRunner)
    config = ROIConfig(
        hero_card_1=ROIRegion(0, 0, 10, 10),
        hero_card_2=ROIRegion(10, 0, 10, 10),
        pot_size=ROIRegion(20, 0, 10, 10),
        bet_to_call=ROIRegion(30, 0, 10, 10),
        hero_stack=ROIRegion(40, 0, 10, 10),
        action_buttons=ROIRegion(50, 0, 20, 10),
        villain_stacks=[ROIRegion(70, 0, 10, 10)],
    )

    runner._init_frame_buffer(config)

    names = {roi.name for roi in runner._frame_buffer.roi_regions}
    assert "action_buttons" in names
    assert "bet_to_call" in names
    assert "hero_stack" in names
    assert "villain_stack_0" in names


def test_idle_metrics_clear_recommendation_without_active_hero_cards():
    runner = PipelineRunner.__new__(PipelineRunner)

    metrics = runner._idle_metrics("NO_ACTIVE_HERO_CARDS")

    assert metrics.recommendation == "WAIT"
    assert metrics.parse_status == "NO_ACTIVE_HERO_CARDS"
    assert metrics.action_mode == "none"
    assert metrics.equity == 0.0
