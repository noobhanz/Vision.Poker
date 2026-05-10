"""
Setup script to build vision.poker as a macOS .app bundle.

Usage:
    pip install py2app
    python setup_app.py py2app

This creates a standalone .app in the dist/ folder that can be:
- Double-clicked to run
- Dragged to Applications folder
- Set to launch at login
"""

from setuptools import setup

APP = ['app.py']
DATA_FILES = [
    ('config/skins', ['config/skins/pokerstars.json', 'config/skins/gg_poker.json']),
    ('overlay', ['overlay/styles.qss']),
]
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'Vision Poker',
        'CFBundleDisplayName': 'Vision Poker',
        'CFBundleIdentifier': 'poker.vision.hud',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # Makes it a menu bar app (no dock icon)
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Vision Poker needs accessibility access to detect poker windows.',
        'NSScreenCaptureUsageDescription': 'Vision Poker needs screen recording access to capture the poker table.',
    },
    'packages': [
        'capture',
        'vision',
        'engine',
        'overlay',
        'pipeline',
        'config',
        'rumps',
        'PyQt6',
        'numpy',
        'mss',
        'PIL',
    ],
    'includes': [
        'pydantic',
        'pydantic_settings',
    ],
    'excludes': [
        'ultralytics',  # Exclude YOLO for smaller bundle, use template matching
        'torch',
        'easyocr',  # Exclude for smaller bundle initially
    ],
    'iconfile': None,  # Add icon.icns here if you have one
}

setup(
    app=APP,
    name='Vision Poker',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
