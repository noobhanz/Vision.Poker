#!/bin/bash
# Double-click this file to launch the Vision Poker live-readiness controller.

cd "$(dirname "$0")"

PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

"$PYTHON" -m tools.live_screen_hud --controller
