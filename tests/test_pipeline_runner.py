import pytest

pytest.importorskip("mss")

import asyncio
import numpy as np

from config.settings import Settings
from engine.models import GameState
from pipeline.runner import PipelineRunner
from pipeline.stability import StateStabilizer
from capture.window_finder import WindowRect
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


def test_compute_metrics_is_neutral_for_warning_status():
    runner = PipelineRunner.__new__(PipelineRunner)

    metrics = runner._compute_metrics(
        GameState(
            hero_cards=["Ah", "Kh"],
            board_cards=[],
            pot_size=20.0,
            bet_to_call=0.0,
            hero_stack=2.0,
            action_mode="decision",
            confidence=0.8,
        ),
        "BOARD_CARDS_UNREADABLE",
    )

    assert metrics.recommendation == "WAIT"
    assert metrics.parse_status == "BOARD_CARDS_UNREADABLE"
    assert metrics.equity == 0.0
    assert metrics.ev_call == 0.0


def test_compute_metrics_does_not_recommend_raise_without_call_price():
    runner = PipelineRunner.__new__(PipelineRunner)
    runner.settings = Settings(monte_carlo_n=10)

    metrics = runner._compute_metrics(
        GameState(
            hero_cards=["Ah", "Jc"],
            board_cards=["Ac", "Ts", "2d"],
            pot_size=0.20,
            bet_to_call=0.0,
            hero_stack=1.94,
            action_mode="decision",
            legal_actions=["check", "bet"],
            action_amounts={"bet": 0.02},
            confidence=0.94,
        ),
        "OK",
    )

    assert metrics.recommendation == "CHECK OPTION"
    assert metrics.required_equity == 0.0
    assert metrics.ev_call == 0.0


class StableParser:
    def __init__(self, state):
        self.state = state

    def parse_with_fallback(self, frame, roi_config, min_confidence=0.6):
        return self.state, "OK"


class EmptyParser:
    def parse_with_fallback(self, frame, roi_config, min_confidence=0.6):
        return None, "NO_ACTIVE_HERO_CARDS"


def test_process_frame_waits_for_repeated_active_parse():
    runner = PipelineRunner.__new__(PipelineRunner)
    runner.settings = Settings(stable_frames_required=2, monte_carlo_n=10)
    runner.roi_config = ROIConfig()
    runner._stabilizer = StateStabilizer(runner.settings.stable_frames_required)
    runner._hud = None
    runner.state_parser = StableParser(
        GameState(
            hero_cards=["Ah", "Kh"],
            board_cards=[],
            pot_size=0.03,
            bet_to_call=0.02,
            hero_stack=2.0,
            action_mode="decision",
            legal_actions=["fold", "call", "raise"],
            action_amounts={"call": 0.02, "raise": 0.04},
            confidence=0.95,
        )
    )

    rect = WindowRect(0, 0, 100, 100, window_id=1)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    first = asyncio.run(runner.process_frame(frame, rect))
    second = asyncio.run(runner.process_frame(frame, rect))

    assert first is None
    assert second is not None
    assert second.parse_status == "OK"


def test_process_frame_emits_idle_without_stability_delay():
    runner = PipelineRunner.__new__(PipelineRunner)
    runner.settings = Settings(stable_frames_required=3, monte_carlo_n=10)
    runner.roi_config = ROIConfig()
    runner._stabilizer = StateStabilizer(runner.settings.stable_frames_required)
    runner._stabilizer._pending_key = ("stale",)
    runner._stabilizer._pending_count = 2
    runner._hud = None
    runner.state_parser = EmptyParser()

    metrics = asyncio.run(
        runner.process_frame(
            np.zeros((100, 100, 3), dtype=np.uint8),
            WindowRect(0, 0, 100, 100, window_id=1),
        )
    )

    assert metrics is not None
    assert metrics.parse_status == "NO_ACTIVE_HERO_CARDS"
    assert runner._stabilizer.pending_key is None
