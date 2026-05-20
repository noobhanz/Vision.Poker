#!/usr/bin/env python3
"""Run the Vision Poker HUD against any visible window on the screen.

This is the live-readiness bridge for recorded testing: open a cropped poker
recording in VLC/QuickTime, then point this tool at the player window. Unlike
``tools.replay_hud``, this reads pixels through the normal screen-capture path.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np

from capture.screen import ScreenCapture
from capture.window_finder import WindowRect, list_windows

if TYPE_CHECKING:
    from engine.models import Metrics
    from pipeline.runner import PipelineRunner


@dataclass(frozen=True)
class CropMargins:
    """Pixel margins to remove from a captured window before parsing."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0


def crop_frame_for_live_read(
    frame: np.ndarray,
    rect: WindowRect,
    crop: CropMargins,
) -> tuple[np.ndarray, WindowRect]:
    """Crop a captured player/window frame and return matching parser rect."""
    height, width = frame.shape[:2]
    left = max(0, min(crop.left, width))
    top = max(0, min(crop.top, height))
    right = max(left, min(width - max(0, crop.right), width))
    bottom = max(top, min(height - max(0, crop.bottom), height))

    cropped = frame[top:bottom, left:right]
    cropped_rect = WindowRect(
        x=rect.x + left,
        y=rect.y + top,
        width=max(0, right - left),
        height=max(0, bottom - top),
        window_id=rect.window_id,
        title=rect.title,
    )
    return cropped, cropped_rect


def build_runner(args: argparse.Namespace) -> PipelineRunner:
    """Create a pipeline runner configured for visible-window live testing."""
    from config.settings import Settings
    from pipeline.runner import PipelineRunner

    settings = Settings(
        poker_client_title=args.title,
        skin_config=args.skin,
        capture_fps=args.fps,
        monte_carlo_n=args.monte_carlo,
        stable_frames_required=args.stable_frames,
        debug_mode=args.debug,
        multi_table_mode=False,
    )
    return PipelineRunner(settings)


def format_metrics(metrics: Optional["Metrics"]) -> str:
    """Return a compact status string for debug output."""
    if metrics is None:
        return "waiting_for_stability"
    return (
        f"{metrics.parse_status} {metrics.street.value} "
        f"equity={metrics.equity * 100:.1f}% "
        f"pot_odds={metrics.pot_odds * 100:.1f}% "
        f"ev={metrics.ev_call:.2f} rec={metrics.recommendation} "
        f"mode={metrics.action_mode}"
    )


class LiveScreenHudSession:
    """Own the running HUD/capture loop for one visible source window."""

    def __init__(
        self,
        args: argparse.Namespace,
        *,
        status_callback=None,
    ):
        self.args = args
        self.status_callback = status_callback
        self.runner = build_runner(args)
        self.capture = ScreenCapture(title_substring=args.title, mode="title")
        self.crop = CropMargins(
            left=args.crop_left,
            top=args.crop_top,
            right=args.crop_right,
            bottom=args.crop_bottom,
        )
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.timer = None
        self.hud = None
        self.state = {
            "pending_future": None,
            "last_signature": None,
            "window_missing": False,
        }

    def start(self, app) -> None:
        """Create the HUD and start polling the target window."""
        from PyQt6.QtCore import QTimer

        from overlay.hud import create_hud_app

        _, self.hud = create_hud_app(
            hotkey=self.args.hotkey,
            opacity=self.args.opacity,
            position=self.args.position,
            standalone=True,
            always_on_top=self.args.always_on_top,
        )
        if self.args.hud_x is not None and self.args.hud_y is not None:
            self.hud.move(self.args.hud_x, self.args.hud_y)
        self.hud.show()
        self.hud.set_status("WATCHING")

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(max(1, int(1000 / self.args.fps)))
        self.tick()
        self._set_status(f"Watching: {self.args.title}")

    def stop(self) -> None:
        """Stop polling and close the HUD."""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        pending = self.state.get("pending_future")
        if pending is not None:
            pending.cancel()
            self.state["pending_future"] = None
        if self.hud is not None:
            self.hud.close()
            self.hud = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        self._set_status("Stopped")

    def _set_status(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

    def _reset_for_signature(self, signature) -> None:
        if self.state["last_signature"] == signature:
            return
        self.state["last_signature"] = signature
        self.runner._stabilizer.reset()
        self.runner._frame_buffer = None
        self.runner._frame_buffer_signature = None

    def _handle_pending_result(self) -> None:
        pending = self.state["pending_future"]
        if pending is None or not pending.done():
            return

        try:
            metrics = pending.result()
        except Exception as exc:
            metrics = None
            if self.args.debug:
                print(f"live_screen_hud processing failed: {exc}", file=sys.stderr)

        self.state["pending_future"] = None
        if metrics is not None and self.hud is not None:
            self.hud.update_metrics(metrics)
            self.hud.set_status("LIVE TEST")
            self._set_status(format_metrics(metrics))
        elif self.args.debug:
            print(format_metrics(metrics))

    def tick(self) -> None:
        """Capture and process the target window once if the worker is free."""
        self._handle_pending_result()
        if self.state["pending_future"] is not None:
            return

        rect = self.capture.find_window()
        if rect is None:
            if not self.state["window_missing"]:
                print(
                    f"Waiting for visible window containing title: {self.args.title!r}",
                    file=sys.stderr,
                )
            self.state["window_missing"] = True
            if self.hud is not None:
                self.hud.set_status("NO WINDOW", is_warning=True)
            self._set_status(f"No window found for: {self.args.title}")
            return
        self.state["window_missing"] = False

        frame = self.capture.capture_rect(rect)
        if frame is None:
            if self.hud is not None:
                self.hud.set_status("CAPTURE FAILED", is_warning=True)
            self._set_status("Capture failed. Check Screen Recording permission.")
            return

        frame, parser_rect = crop_frame_for_live_read(frame, rect, self.crop)
        if frame.size == 0 or parser_rect.width <= 0 or parser_rect.height <= 0:
            if self.hud is not None:
                self.hud.set_status("BAD CROP", is_warning=True)
            self._set_status("Bad crop. Reduce crop margins.")
            return

        signature = (
            parser_rect.window_id,
            parser_rect.width,
            parser_rect.height,
            self.crop,
        )
        self._reset_for_signature(signature)

        if self.args.follow_window and self.hud is not None:
            self.hud.position_over_window(parser_rect)

        self.state["pending_future"] = self.executor.submit(
            lambda current_frame=frame.copy(), current_rect=parser_rect: asyncio.run(
                self.runner.process_frame(current_frame, current_rect)
            )
        )


def run_hud(args: argparse.Namespace) -> int:
    """Run a standalone HUD that reads a visible external window."""
    from PyQt6.QtCore import QTimer

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    session = LiveScreenHudSession(args)
    session.start(app)
    try:
        return app.exec()
    finally:
        session.stop()


def run_controller_app(args: argparse.Namespace) -> int:
    """Run a small product-facing controller for recording/live-window tests."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Vision Poker Live Readiness")
    window.setObjectName("LiveReadinessController")
    window.setMinimumWidth(640)
    window.resize(760, 430)

    layout = QVBoxLayout(window)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)

    brand_layout = QHBoxLayout()
    brand_layout.setContentsMargins(0, 0, 0, 0)
    brand_layout.setSpacing(0)
    brand_vision = QLabel("VISION.")
    brand_vision.setObjectName("brand_vision")
    brand_poker = QLabel("POKER")
    brand_poker.setObjectName("brand_poker")
    brand_layout.addWidget(brand_vision)
    brand_layout.addWidget(brand_poker)
    brand_layout.addStretch()
    layout.addLayout(brand_layout)

    subtitle = QLabel(
        "Test the real HUD against a visible recording window before going live."
    )
    subtitle.setObjectName("metric_label")
    layout.addWidget(subtitle)

    window_select = QComboBox()
    window_select.setToolTip(
        "Visible windows macOS can see. Pick VLC, QuickTime, or a PokerStars table."
    )
    title_input = QLineEdit(args.title or "")
    title_input.setPlaceholderText("VLC, QuickTime Player, Screen Recording, PokerStars...")
    title_input.setToolTip(
        "The app captures the first visible window whose title or app name contains this text."
    )

    def refresh_windows() -> None:
        current = title_input.text()
        window_select.clear()
        for owner, name in list_windows():
            label = f"{owner}: {name}" if name else owner
            if label.strip():
                window_select.addItem(label, owner or name)
        if current:
            title_input.setText(current)

    def use_selected_window() -> None:
        data = window_select.currentData()
        text = data or window_select.currentText()
        if text:
            title_input.setText(text)

    refresh_windows()
    window_select.currentIndexChanged.connect(use_selected_window)

    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.addRow("Detected windows", window_select)
    form.addRow("Window title contains", title_input)

    fps_spin = QSpinBox()
    fps_spin.setRange(1, 30)
    fps_spin.setValue(args.fps)
    fps_spin.setToolTip(
        "How many times per second Vision Poker reads the visible window. "
        "Higher is smoother but uses more CPU."
    )
    stable_spin = QSpinBox()
    stable_spin.setRange(1, 6)
    stable_spin.setValue(args.stable_frames)
    stable_spin.setToolTip(
        "How many consecutive matching reads are required before the HUD updates. "
        "Higher values reduce flicker and false reads."
    )
    monte_spin = QSpinBox()
    monte_spin.setRange(10, 5000)
    monte_spin.setSingleStep(10)
    monte_spin.setValue(args.monte_carlo)
    monte_spin.setToolTip(
        "Number of simulations used for equity. Higher can be more precise but slower."
    )
    form.addRow("Capture FPS", fps_spin)
    form.addRow("Stable frames", stable_spin)
    form.addRow("Monte Carlo", monte_spin)

    crop_left = QSpinBox()
    crop_top = QSpinBox()
    crop_right = QSpinBox()
    crop_bottom = QSpinBox()
    for spin, value in [
        (crop_left, args.crop_left),
        (crop_top, args.crop_top),
        (crop_right, args.crop_right),
        (crop_bottom, args.crop_bottom),
    ]:
        spin.setRange(0, 500)
        spin.setValue(value)
        spin.setToolTip(
            "Trim pixels from the recording/player window before parsing. Use this "
            "only if player controls or borders are inside the captured image."
        )

    crop_row = QHBoxLayout()
    crop_row.addWidget(QLabel("L"))
    crop_row.addWidget(crop_left)
    crop_row.addWidget(QLabel("T"))
    crop_row.addWidget(crop_top)
    crop_row.addWidget(QLabel("R"))
    crop_row.addWidget(crop_right)
    crop_row.addWidget(QLabel("B"))
    crop_row.addWidget(crop_bottom)
    form.addRow("Crop margins", crop_row)
    layout.addLayout(form)

    help_text = QLabel(
        "Recommended: open a cropped recording in VLC or QuickTime, select that "
        "window, keep crop margins at 0 unless the player controls are captured, "
        "then press Start HUD."
    )
    help_text.setObjectName("controller_help")
    help_text.setWordWrap(True)
    layout.addWidget(help_text)

    status = QLabel("Stopped")
    status.setObjectName("confidence")
    status.setWordWrap(True)

    start_button = QPushButton("Start HUD")
    stop_button = QPushButton("Stop HUD")
    stop_button.setEnabled(False)
    refresh_button = QPushButton("Refresh Windows")

    buttons = QHBoxLayout()
    buttons.addWidget(start_button)
    buttons.addWidget(stop_button)
    buttons.addStretch()
    buttons.addWidget(refresh_button)
    layout.addLayout(buttons)
    layout.addWidget(status)

    controller_style = """
    QWidget#LiveReadinessController {
        background-color: #060910;
        color: #f2f5f8;
    }
    QWidget#LiveReadinessController QLabel {
        background-color: transparent;
    }
    QWidget#LiveReadinessController QLabel#brand_vision {
        color: #f6f8fb;
        font-size: 18px;
        font-weight: bold;
        padding: 0px;
    }
    QWidget#LiveReadinessController QLabel#brand_poker {
        color: #38f68d;
        font-size: 18px;
        font-weight: bold;
        padding: 0px;
    }
    QWidget#LiveReadinessController QLabel#metric_label {
        color: #a7b0c0;
        font-size: 13px;
        padding: 0px;
    }
    QWidget#LiveReadinessController QLabel#controller_help {
        color: #a7b0c0;
        font-size: 12px;
        padding: 10px 12px;
        border: 1px solid rgba(56, 246, 141, 0.22);
        border-radius: 6px;
        background-color: rgba(56, 246, 141, 0.06);
    }
    QWidget#LiveReadinessController QLabel#confidence {
        color: #a7b0c0;
        font-size: 12px;
        padding: 4px 0px;
    }
    QWidget#LiveReadinessController QComboBox,
    QWidget#LiveReadinessController QLineEdit,
    QWidget#LiveReadinessController QSpinBox {
        background-color: #101722;
        color: #f2f5f8;
        border: 1px solid rgba(167, 176, 192, 0.35);
        border-radius: 5px;
        padding: 5px 8px;
        selection-background-color: #38f68d;
    }
    QWidget#LiveReadinessController QComboBox:focus,
    QWidget#LiveReadinessController QLineEdit:focus,
    QWidget#LiveReadinessController QSpinBox:focus {
        border: 1px solid rgba(56, 246, 141, 0.75);
    }
    QWidget#LiveReadinessController QPushButton {
        background-color: rgba(56, 246, 141, 0.14);
        color: #f2f5f8;
        border: 1px solid rgba(56, 246, 141, 0.55);
        border-radius: 5px;
        padding: 7px 12px;
        font-weight: bold;
    }
    QWidget#LiveReadinessController QPushButton:hover {
        background-color: rgba(56, 246, 141, 0.22);
        border: 1px solid rgba(56, 246, 141, 0.85);
    }
    QWidget#LiveReadinessController QPushButton:disabled {
        background-color: rgba(124, 135, 152, 0.14);
        color: #7c8798;
        border: 1px solid rgba(124, 135, 152, 0.2);
    }
    QWidget#LiveReadinessController QToolTip {
        background-color: #101722;
        color: #f2f5f8;
        border: 1px solid rgba(56, 246, 141, 0.75);
        padding: 8px;
        font-size: 12px;
        border-radius: 4px;
    }
    """
    window.setStyleSheet(controller_style)

    current_session: dict[str, Optional[LiveScreenHudSession]] = {"session": None}

    def stop_session() -> None:
        session = current_session.get("session")
        if session is not None:
            session.stop()
            current_session["session"] = None
        start_button.setEnabled(True)
        stop_button.setEnabled(False)

    def start_session() -> None:
        if not title_input.text().strip():
            status.setText("Choose or type a visible window title first.")
            return
        stop_session()
        session_args = argparse.Namespace(**vars(args))
        session_args.title = title_input.text().strip()
        session_args.fps = fps_spin.value()
        session_args.stable_frames = stable_spin.value()
        session_args.monte_carlo = monte_spin.value()
        session_args.crop_left = crop_left.value()
        session_args.crop_top = crop_top.value()
        session_args.crop_right = crop_right.value()
        session_args.crop_bottom = crop_bottom.value()
        session_args.always_on_top = True
        session = LiveScreenHudSession(
            session_args,
            status_callback=status.setText,
        )
        current_session["session"] = session
        session.start(app)
        start_button.setEnabled(False)
        stop_button.setEnabled(True)

    start_button.clicked.connect(start_session)
    stop_button.clicked.connect(stop_session)
    refresh_button.clicked.connect(refresh_windows)

    window.destroyed.connect(lambda *_: stop_session())
    window.show()
    return app.exec()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Vision Poker as a live HUD against a visible VLC/QuickTime/"
            "PokerStars window"
        ),
    )
    parser.add_argument(
        "--title",
        default=None,
        help=(
            "Substring of the visible window title to capture, e.g. "
            "'VLC', 'QuickTime Player', 'Screen Recording', or 'PokerStars'"
        ),
    )
    parser.add_argument("--skin", "-s", default="pokerstars_mac_cash")
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--monte-carlo", "-n", type=int, default=100)
    parser.add_argument("--stable-frames", type=int, default=2)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--always-on-top", action="store_true")
    parser.add_argument("--follow-window", action="store_true")
    parser.add_argument("--hud-x", type=int, default=None)
    parser.add_argument("--hud-y", type=int, default=None)
    parser.add_argument("--hotkey", default="F9")
    parser.add_argument("--opacity", type=float, default=1.0)
    parser.add_argument(
        "--position",
        default="top-right",
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
    )
    parser.add_argument("--crop-left", type=int, default=0)
    parser.add_argument("--crop-top", type=int, default=0)
    parser.add_argument("--crop-right", type=int, default=0)
    parser.add_argument("--crop-bottom", type=int, default=0)
    parser.add_argument(
        "--controller",
        action="store_true",
        help="Open the standalone Vision Poker live-readiness controller",
    )

    args = parser.parse_args()
    if args.fps <= 0:
        parser.error("--fps must be greater than 0")
    if args.stable_frames <= 0:
        parser.error("--stable-frames must be greater than 0")
    if args.monte_carlo <= 0:
        parser.error("--monte-carlo must be greater than 0")
    if (args.hud_x is None) != (args.hud_y is None):
        parser.error("--hud-x and --hud-y must be provided together")
    for name in ("crop_left", "crop_top", "crop_right", "crop_bottom"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} cannot be negative")
    return args


def main() -> None:
    args = parse_args()
    if args.controller or not args.title:
        raise SystemExit(run_controller_app(args))
    raise SystemExit(run_hud(args))


if __name__ == "__main__":
    main()
