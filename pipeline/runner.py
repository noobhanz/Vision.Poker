"""
Main async event loop:
1. Capture frame (2fps)
2. Check frame buffer (skip if no change)
3. Run card detection + OCR (parallel where possible)
4. Parse GameState
5. Compute Metrics (equity + pot odds + draws)
6. Emit Metrics to HUD via Qt signal

Target latency: <300ms from capture to HUD update.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

from capture.frame_buffer import ROI, FrameBuffer
from capture.screen import ScreenCapture
from capture.window_finder import WindowRect
from config.settings import Settings
from engine.draws import classify_draw, count_outs, made_hand_description
from engine.equity import calculate_equity
from engine.ev import ev_call, ev_fold, recommendation
from engine.models import DrawType, Metrics, Street
from engine.pot_odds import pot_odds, required_equity
from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import ROIConfig, load_skin_config
from vision.state_parser import StateParser

from .ipc import MetricsQueue
from .stability import StateStabilizer


class PipelineRunner:
    """
    Main pipeline coordinating capture → vision → engine → overlay.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the pipeline.

        Args:
            settings: Application settings (loads from .env if None)
        """
        self.settings = settings or Settings()

        # Initialize components
        # Use active window mode for multi-table support
        capture_mode = "active" if self.settings.multi_table_mode else "title"
        self.screen_capture = ScreenCapture(
            title_substring=self.settings.poker_client_title,
            mode=capture_mode,
        )
        self.card_detector = CardDetector(
            model_path=self.settings.yolo_model_path,
            confidence_threshold=self.settings.confidence_threshold,
        )
        self.ocr_engine = OCREngine()
        self.state_parser = StateParser(
            card_detector=self.card_detector,
            ocr_engine=self.ocr_engine,
        )

        # Load ROI config
        try:
            self.roi_config = load_skin_config(self.settings.skin_config)
        except FileNotFoundError:
            print(f"Skin config '{self.settings.skin_config}' not found, using defaults")
            self.roi_config = ROIConfig()

        # Frame buffer for change detection
        self._frame_buffer: Optional[FrameBuffer] = None
        self._frame_buffer_signature: Optional[tuple[Optional[int], int, int]] = None

        # Output queue for HUD
        self.metrics_queue = MetricsQueue()

        # State
        self._running = False
        self._last_metrics: Optional[Metrics] = None
        self._stabilizer = StateStabilizer(self.settings.stable_frames_required)
        self._hud = None

    def _init_frame_buffer(self, roi_config: ROIConfig) -> None:
        """Initialize frame buffer with ROI regions."""
        rois = []

        def add_roi(region, name: str) -> None:
            if region:
                rois.append(
                    ROI(
                        x=int(region.x),
                        y=int(region.y),
                        width=int(region.w),
                        height=int(region.h),
                        name=name,
                    )
                )

        # Add card ROIs for change detection
        for i, roi in enumerate(roi_config.get_hero_card_rois()):
            add_roi(roi, f"hero_card_{i}")

        for i, roi in enumerate(roi_config.get_board_card_rois()):
            add_roi(roi, f"board_card_{i}")

        # Include all visible state that can change HUD decisions.
        add_roi(roi_config.pot_size, "pot_size")
        add_roi(roi_config.bet_to_call, "bet_to_call")
        add_roi(roi_config.hero_stack, "hero_stack")
        add_roi(roi_config.action_buttons, "action_buttons")
        for i, roi in enumerate(roi_config.villain_stacks):
            add_roi(roi, f"villain_stack_{i}")

        self._frame_buffer = FrameBuffer(rois)

    def _compute_metrics(self, state, parse_status: str = "OK") -> Metrics:
        """Compute all metrics from game state."""
        if parse_status != "OK":
            return Metrics(
                equity=0.0,
                pot_odds=0.0,
                required_equity=0.0,
                ev_call=0.0,
                ev_fold=0.0,
                outs=0,
                draw_type=DrawType.NONE,
                made_hand_rank="",
                recommendation="WAIT",
                confidence=state.confidence,
                street=state.street,
                parse_status=parse_status,
                action_mode=state.action_mode,
            )

        # Calculate equity
        equity = calculate_equity(
            hero=state.hero_cards,
            board=state.board_cards,
            num_opponents=max(1, state.num_players - 1),
            n=self.settings.monte_carlo_n,
        )

        # Calculate pot odds
        po = pot_odds(state.pot_size, state.bet_to_call)
        req_eq = required_equity(state.pot_size, state.bet_to_call)

        # Calculate EV
        ev = ev_call(equity, state.pot_size, state.bet_to_call)
        ev_f = ev_fold()

        # Calculate draws
        outs = count_outs(state.hero_cards, state.board_cards)
        draw_type = classify_draw(state.hero_cards, state.board_cards)
        made_hand = made_hand_description(state.hero_cards, state.board_cards)

        # Get recommendation only when hero has an actual decision.
        if state.action_mode == "decision" and parse_status == "OK":
            rec = recommendation(ev, equity, req_eq)
        else:
            rec = "WAIT"

        return Metrics(
            equity=equity,
            pot_odds=po,
            required_equity=req_eq,
            ev_call=ev,
            ev_fold=ev_f,
            outs=outs,
            draw_type=draw_type,
            made_hand_rank=made_hand,
            recommendation=rec,
            confidence=state.confidence,
            street=state.street,
            parse_status=parse_status,
            action_mode=state.action_mode,
        )

    def _idle_metrics(self, parse_status: str) -> Metrics:
        """Return a conservative HUD state when no active hero hand is readable."""
        return Metrics(
            equity=0.0,
            pot_odds=0.0,
            required_equity=0.0,
            ev_call=0.0,
            ev_fold=0.0,
            outs=0,
            draw_type=DrawType.NONE,
            made_hand_rank="",
            recommendation="WAIT",
            confidence=0.0,
            street=Street.PREFLOP,
            parse_status=parse_status,
            action_mode="none",
        )

    async def process_frame(self, frame: np.ndarray, rect: WindowRect) -> Optional[Metrics]:
        """
        Process a single frame through the pipeline.

        Args:
            frame: Captured frame as np.ndarray (BGR)
            rect: Window rectangle

        Returns:
            Computed Metrics or None if processing fails
        """
        start_time = time.time()

        # Scale ROI config to match window size
        scaled_config = self.roi_config.scale_to_window(rect.width, rect.height)

        # Parse game state
        state, status = self.state_parser.parse_with_fallback(
            frame, scaled_config, min_confidence=0.6
        )

        if state is None:
            if self.settings.debug_mode:
                print(f"State parse failed: {status}")
            self._stabilizer.reset()
            if status == "NO_ACTIVE_HERO_CARDS":
                return self._idle_metrics(status)
            return None

        stability = self._stabilizer.observe(state, status)
        if not stability.is_stable:
            if self.settings.debug_mode:
                print(
                    "Waiting for stable parse "
                    f"({stability.count}/{stability.required}): {status}"
                )
            return None

        # Compute metrics
        try:
            metrics = self._compute_metrics(state, status)
        except Exception as e:
            if self.settings.debug_mode:
                print(f"Metrics computation failed: {e}")
            return None

        elapsed = time.time() - start_time
        if self.settings.debug_mode:
            print(f"Frame processed in {elapsed*1000:.1f}ms")

        return metrics

    async def run(self) -> None:
        """Main pipeline loop."""
        self._running = True
        interval = 1.0 / self.settings.capture_fps

        print(f"Starting pipeline, looking for window: '{self.settings.poker_client_title}'")
        print(f"Capture FPS: {self.settings.capture_fps}")
        print(f"Press {self.settings.hud_hotkey} to toggle HUD visibility")

        while self._running:
            loop_start = time.time()

            # Find and capture window
            rect = self.screen_capture.find_window()
            if rect is None:
                if self.settings.debug_mode:
                    print("Poker window not found, waiting...")
                await asyncio.sleep(interval)
                continue

            frame = self.screen_capture.capture_rect(rect)
            if frame is None:
                await asyncio.sleep(interval)
                continue

            scaled_config = self.roi_config.scale_to_window(rect.width, rect.height)
            signature = (rect.window_id, rect.width, rect.height)

            # Initialize or reset frame buffer when the tracked table changes.
            if (
                self._frame_buffer is None
                or self._frame_buffer_signature != signature
            ):
                self._init_frame_buffer(scaled_config)
                self._frame_buffer_signature = signature

            # Check for changes
            if not self._frame_buffer.has_changed(frame):
                # No change, skip processing
                await asyncio.sleep(interval)
                continue

            # Process frame
            metrics = await self.process_frame(frame, rect)

            if metrics is not None:
                self._last_metrics = metrics
                await self.metrics_queue.put(metrics)

                # Update HUD if connected
                if self._hud is not None:
                    self._hud.update_metrics(metrics)
                    self._hud.position_over_window(rect)

            # Maintain frame rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        """Stop the pipeline."""
        self._running = False

    def connect_hud(self, hud) -> None:
        """Connect a HUD widget to receive metrics updates."""
        self._hud = hud


def run_with_qt(settings: Optional[Settings] = None) -> None:
    """
    Run the pipeline with Qt event loop integration.
    """
    import threading
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    from overlay.hud import create_hud_app

    settings = settings or Settings()

    # Create Qt app and HUD
    app, hud = create_hud_app(
        hotkey=settings.hud_hotkey,
        opacity=settings.hud_opacity,
        position=settings.hud_position,
    )

    # Create pipeline
    pipeline = PipelineRunner(settings)
    pipeline.connect_hud(hud)

    # Run pipeline in background thread
    def run_pipeline():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(pipeline.run())
        finally:
            loop.close()

    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()

    # Show HUD and run Qt event loop
    hud.show()
    sys.exit(app.exec())


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="vision.poker Overlay HUD")
    parser.add_argument(
        "--window",
        "-w",
        default=None,
        help="Poker client window title to search for",
    )
    parser.add_argument(
        "--skin",
        "-s",
        default=None,
        help="Skin configuration to use (e.g., pokerstars, gg_poker)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Capture frames per second",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run without GUI (prints metrics to console)",
    )

    args = parser.parse_args()

    # Load settings
    settings = Settings()

    # Override with command line args
    if args.window:
        settings.poker_client_title = args.window
    if args.skin:
        settings.skin_config = args.skin
    if args.fps:
        settings.capture_fps = args.fps
    if args.debug:
        settings.debug_mode = True

    if args.no_gui:
        # Console mode
        async def console_run():
            pipeline = PipelineRunner(settings)

            async def print_metrics():
                while True:
                    metrics = await pipeline.metrics_queue.get()
                    if metrics:
                        print(f"\n--- Metrics ---")
                        print(f"Equity: {metrics.equity*100:.1f}%")
                        print(f"Pot Odds: {metrics.pot_odds*100:.1f}%")
                        print(f"EV(call): ${metrics.ev_call:.2f}")
                        print(f"Recommendation: {metrics.recommendation}")
                        print(f"Made Hand: {metrics.made_hand_rank}")

            # Run both tasks
            await asyncio.gather(
                pipeline.run(),
                print_metrics(),
            )

        asyncio.run(console_run())
    else:
        # GUI mode
        run_with_qt(settings)


if __name__ == "__main__":
    main()
