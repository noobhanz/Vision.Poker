# vision.poker

> Real-time poker HUD overlay for game state analysis

<p align="center">
  <img src="https://img.shields.io/badge/macOS-10.15+-blue" alt="macOS">
  <img src="https://img.shields.io/badge/Python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

A menu bar app that displays real-time poker metrics as a transparent overlay on your poker table:

- **Equity** - Win probability vs opponent range
- **Pot Odds** - Risk/reward ratio
- **EV** - Expected value of calling
- **Draws** - Outs and draw type detection
- **Recommendation** - FOLD / CALL / RAISE suggestion

## Installation

### Quick Install (Recommended)

1. **Download** or clone this repository
2. **Double-click** `Install Vision Poker.command`
3. **Follow** the setup wizard

That's it! Look for **V.P** in your menu bar.

### Manual Install

```bash
# Clone the repository
git clone https://github.com/yourusername/vision-poker.git
cd vision-poker

# Run the installer
python3 install.py
```

## Usage

### Menu Bar App

After installation, vision.poker runs in your **menu bar** (like Magnet or Flux):

1. Click **V.P** in your menu bar
2. Select **Start HUD**
3. The overlay appears on your poker window
4. Press **F9** to toggle visibility

### Command Line

```bash
# Run menu bar app
python3 app.py

# Run with custom poker client
python3 -m pipeline.runner --window "GGPoker"

# Console mode (no GUI)
python3 -m pipeline.runner --no-gui
```

## Supported Poker Clients

Built-in support for:
- PokerStars
- GGPoker

Other clients work with manual ROI calibration.

## Settings

Click **V.P > Settings** in the menu bar, or edit `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `POKER_CLIENT_TITLE` | PokerStars | Window title to find |
| `HUD_POSITION` | top-right | Overlay position |
| `HUD_HOTKEY` | F9 | Toggle overlay |
| `HUD_OPACITY` | 0.88 | Transparency (0-1) |
| `CAPTURE_FPS` | 2 | Capture rate |

## Custom Poker Clients

```bash
# Open calibration tool
python -m tools.calibrate_roi --window "YourPokerClient" --output custom.json

# Controls:
# - Click and drag to draw regions
# - Press 1-7 for hero/board cards
# - Press p/b/h/v for pot/bet/hero stack/villain stack
# - Press 's' to save, 'q' to quit
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Test with sample frames
python -m tools.replay_test --input tests/fixtures/sample_frames/ --skin pokerstars
```

## Project Structure

```
vision-poker/
├── capture/           # Screen capture module
├── vision/            # Card detection and OCR
├── engine/            # Poker math (equity, pot odds, EV)
├── overlay/           # PyQt6 HUD
├── pipeline/          # Main async pipeline
├── config/            # Settings and skin configs
├── tools/             # Development utilities
└── tests/             # Test suite
```

## How It Works

1. **Capture**: `mss` captures the poker window region at 2fps
2. **Frame Buffer**: `imagehash` pHash detects if game state changed
3. **Card Detection**: YOLOv8 detects cards, falls back to template matching
4. **OCR**: EasyOCR extracts numeric values from text regions
5. **State Parser**: Validates and combines detections into GameState
6. **Engine**: Computes equity (Monte Carlo), pot odds, EV, draws
7. **HUD**: PyQt6 renders metrics in transparent overlay

## Metrics Displayed

| Metric | Description |
|--------|-------------|
| Equity | Win probability vs random range |
| Pot Odds | bet_to_call / (pot + bet_to_call) |
| Required Eq | Minimum equity to break even |
| EV (call) | Expected value of calling |
| Outs | Number of cards that improve hand |
| Draw Type | Flush draw, OESD, gutshot, etc. |
| Made Hand | Current hand strength description |
| Recommendation | FOLD / CALL / RAISE CANDIDATE |

## Platform Notes

### macOS
- Requires Screen Recording permission in System Preferences
- Grant permission to Terminal/IDE running the script

### Windows
- Uses `pygetwindow` for window discovery
- HUD has click-through enabled via `WS_EX_TRANSPARENT`

### Linux
- Requires `xdotool`: `sudo apt install xdotool`
- May need compositor for transparent windows

## Limitations

- Requires visible poker window (no minimized capture)
- Card detection accuracy depends on skin/theme
- ROI calibration needed for unsupported skins
- OCR may struggle with non-standard fonts

## Explicit Non-Goals

- No automated clicking or action sending
- No memory reading or process injection
- No network communication with poker servers
- No hand history scraping
- No solver/GTO integration

---

*This is a computer vision research project exploring real-time game state extraction. All calculations are performed locally. The system is read-only with respect to the poker client.*
