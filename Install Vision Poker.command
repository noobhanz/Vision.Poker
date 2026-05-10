#!/bin/bash
#
#  vision.poker - True One-Click Installer
#
#  Double-click to install. Everything is automatic.
#  Native macOS experience - no terminal knowledge needed.
#

cd "$(dirname "$0")"

# ============================================
# HELPER FUNCTIONS - Native macOS Dialogs
# ============================================

show_progress() {
    osascript <<EOF
        tell application "System Events"
            display notification "$1" with title "Vision Poker" subtitle "$2"
        end tell
EOF
}

show_dialog() {
    osascript <<EOF
        tell application "System Events"
            display dialog "$1" with title "Vision Poker" buttons {"OK"} default button "OK" with icon note
        end tell
EOF
}

show_error() {
    osascript <<EOF
        tell application "System Events"
            display dialog "$1" with title "Vision Poker" buttons {"OK"} default button "OK" with icon stop
        end tell
EOF
}

show_welcome() {
    osascript <<EOF
        tell application "System Events"
            display dialog "Welcome to vision.poker!

This will install everything you need automatically.

The installation takes about 2-3 minutes." with title "Vision Poker Installer" buttons {"Cancel", "Install"} default button "Install" with icon note
        end tell
EOF
}

show_complete() {
    osascript <<EOF
        tell application "System Events"
            display dialog "Installation Complete!

Vision Poker has been installed successfully.

Look for V.P in your menu bar to get started." with title "Vision Poker" buttons {"Launch Now", "Close"} default button "Launch Now" with icon note
        end tell
EOF
}

show_python_missing() {
    osascript <<EOF
        tell application "System Events"
            display dialog "Python 3 is required but not installed.

Would you like to download it now?" with title "Vision Poker" buttons {"Cancel", "Download Python"} default button "Download Python" with icon caution
        end tell
EOF
}

# ============================================
# PROGRESS WINDOW (Background App)
# ============================================

show_progress_window() {
    osascript <<EOF &
        tell application "System Events"
            set progress description to "Installing vision.poker..."
            set progress additional description to "Preparing..."
            set progress total steps to 100
            set progress completed steps to 0
        end tell
EOF
}

update_progress() {
    # $1 = step number (1-100)
    # $2 = description
    osascript -e "tell application \"System Events\" to display notification \"$2\" with title \"Installing vision.poker...\"" 2>/dev/null
}

# ============================================
# MAIN INSTALLATION
# ============================================

# Show welcome dialog
RESULT=$(show_welcome 2>&1)
if [[ "$RESULT" == *"Cancel"* ]]; then
    exit 0
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    RESULT=$(show_python_missing 2>&1)
    if [[ "$RESULT" == *"Download"* ]]; then
        open "https://www.python.org/downloads/"
        show_dialog "After installing Python, please run this installer again."
    fi
    exit 1
fi

# Start installation with notifications
update_progress 10 "Creating environment..."

# Create virtual environment silently
if [ ! -d "venv" ]; then
    python3 -m venv venv 2>/dev/null
fi
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q 2>/dev/null

update_progress 20 "Installing graphics library..."
pip install PyQt6 -q 2>/dev/null

update_progress 40 "Installing menu bar app..."
pip install rumps -q 2>/dev/null

update_progress 50 "Installing computer vision..."
pip install mss numpy opencv-python Pillow imagehash pydantic-settings -q 2>/dev/null

update_progress 70 "Installing poker engine..."
# Skip heavy optional dependencies for faster install
# pip install easyocr -q 2>/dev/null

update_progress 90 "Finalizing..."

# Create .env if needed
if [ ! -f ".env" ]; then
    cat > .env << 'ENVFILE'
POKER_CLIENT_TITLE=PokerStars
SKIN_CONFIG=pokerstars
CAPTURE_FPS=2
MONTE_CARLO_N=5000
HUD_HOTKEY=F9
HUD_OPACITY=0.88
HUD_POSITION=top-right
DEBUG_MODE=false
ENVFILE
fi

update_progress 100 "Complete!"

# Show completion dialog
RESULT=$(show_complete 2>&1)

# Launch if requested
if [[ "$RESULT" == *"Launch"* ]]; then
    # Launch the graphical wizard for final setup
    python3 installer/wizard.py 2>/dev/null &

    # If wizard isn't available, launch the menu bar app directly
    if [ $? -ne 0 ]; then
        python3 app.py 2>/dev/null &
    fi
fi

exit 0
