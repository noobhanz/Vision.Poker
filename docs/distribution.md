# Desktop App Distribution Guide

This guide covers building and distributing the vision.poker desktop app.

## Building for macOS

### Prerequisites

- macOS 10.15+
- Python 3.10+
- Xcode Command Line Tools

```bash
xcode-select --install
```

### Method 1: py2app (Recommended)

Creates a native `.app` bundle.

```bash
# Install py2app
pip install py2app

# Build the app
python setup_app.py py2app

# Output: dist/Vision Poker.app
```

#### Configuration

The `setup_app.py` file configures the build:

```python
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'Vision Poker',
        'CFBundleIdentifier': 'poker.vision.hud',
        'LSUIElement': True,  # Menu bar app (no dock icon)
        'NSScreenCaptureUsageDescription': 'Vision Poker needs screen recording access.',
    },
    'packages': ['capture', 'vision', 'engine', 'overlay', 'pipeline', 'licensing'],
    'excludes': ['ultralytics', 'torch'],  # Exclude large packages
}
```

#### Test the Build

```bash
# Run the built app
open dist/Vision\ Poker.app

# Check for errors
dist/Vision\ Poker.app/Contents/MacOS/Vision\ Poker
```

### Method 2: PyInstaller

Alternative bundler with broader platform support.

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller --name "Vision Poker" \
    --windowed \
    --onedir \
    --add-data "config/skins:config/skins" \
    --add-data "overlay/styles.qss:overlay" \
    --hidden-import "rumps" \
    --hidden-import "PyQt6" \
    app.py

# Output: dist/Vision Poker/
```

### Creating a DMG Installer

Package the `.app` into a distributable DMG:

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
    --volname "Vision Poker" \
    --volicon "icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "Vision Poker.app" 150 190 \
    --app-drop-link 450 185 \
    "Vision Poker.dmg" \
    "dist/Vision Poker.app"
```

### Code Signing (Required for Distribution)

Without signing, users will see "unidentified developer" warnings.

#### Apple Developer Account

1. Enroll at [developer.apple.com](https://developer.apple.com) ($99/year)
2. Create certificates in Xcode > Preferences > Accounts
3. Download "Developer ID Application" certificate

#### Sign the App

```bash
# Find your signing identity
security find-identity -v -p codesigning

# Sign the app
codesign --force --deep --sign "Developer ID Application: Your Name (TEAMID)" \
    "dist/Vision Poker.app"

# Verify
codesign --verify --verbose "dist/Vision Poker.app"
```

#### Notarization (Required for macOS 10.15+)

Apple must notarize the app for Gatekeeper:

```bash
# Create a zip for upload
ditto -c -k --keepParent "dist/Vision Poker.app" "VisionPoker.zip"

# Submit for notarization
xcrun notarytool submit VisionPoker.zip \
    --apple-id "your@email.com" \
    --password "app-specific-password" \
    --team-id "TEAMID" \
    --wait

# Staple the ticket
xcrun stapler staple "dist/Vision Poker.app"
```

## Building for Windows

### Prerequisites

- Windows 10+
- Python 3.10+
- Visual Studio Build Tools

### Using PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller --name "VisionPoker" ^
    --windowed ^
    --onefile ^
    --add-data "config/skins;config/skins" ^
    --add-data "overlay/styles.qss;overlay" ^
    --icon "icon.ico" ^
    app.py

# Output: dist/VisionPoker.exe
```

### Creating an Installer

Use Inno Setup for a professional installer:

1. Download [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Create `installer.iss`:

```iss
[Setup]
AppName=Vision Poker
AppVersion=1.0.0
DefaultDirName={autopf}\Vision Poker
DefaultGroupName=Vision Poker
OutputBaseFilename=VisionPokerSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\VisionPoker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config\skins\*"; DestDir: "{app}\config\skins"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Vision Poker"; Filename: "{app}\VisionPoker.exe"
Name: "{autodesktop}\Vision Poker"; Filename: "{app}\VisionPoker.exe"

[Run]
Filename: "{app}\VisionPoker.exe"; Description: "Launch Vision Poker"; Flags: postinstall nowait
```

3. Compile: `iscc installer.iss`

### Code Signing for Windows

Use a code signing certificate from DigiCert, Sectigo, etc.

```bash
# Sign with signtool
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com VisionPoker.exe
```

## Auto-Updates

### Implementing Auto-Updates

Add update checking to the app:

```python
# In app.py or a separate updater module
import httpx

def check_for_updates():
    try:
        response = httpx.get("https://api.vision.poker/version")
        latest = response.json()["version"]
        current = "1.0.0"  # Your current version

        if latest > current:
            return {
                "available": True,
                "version": latest,
                "download_url": response.json()["download_url"]
            }
    except:
        pass
    return {"available": False}
```

### Using Sparkle (macOS)

[Sparkle](https://sparkle-project.org/) provides automatic updates:

1. Add Sparkle framework to your app
2. Host an `appcast.xml` file with version info
3. App checks for updates automatically

### Using electron-updater Pattern

For cross-platform updates, host releases on GitHub:

```
https://github.com/user/repo/releases/latest/download/VisionPoker.dmg
https://github.com/user/repo/releases/latest/download/VisionPokerSetup.exe
```

## Distribution Checklist

### Before Release

- [ ] Test on clean machine (no dev dependencies)
- [ ] Verify license validation works
- [ ] Test with real Stripe checkout (use test mode)
- [ ] Update version number
- [ ] Update changelog

### macOS Release

- [ ] Build with py2app or PyInstaller
- [ ] Sign with Developer ID certificate
- [ ] Notarize with Apple
- [ ] Create DMG installer
- [ ] Test DMG on another Mac

### Windows Release

- [ ] Build with PyInstaller
- [ ] Sign with code signing certificate
- [ ] Create installer with Inno Setup
- [ ] Test on clean Windows install

### Upload Release

```bash
# Create GitHub release
gh release create v1.0.0 \
    "VisionPoker.dmg#Vision Poker for macOS" \
    "VisionPokerSetup.exe#Vision Poker for Windows" \
    --title "Vision Poker v1.0.0" \
    --notes "Initial release"
```

## Download URLs

Configure these URLs in the backend:

```python
# In backend/app/main.py
downloads = {
    "mac": "https://github.com/user/repo/releases/latest/download/VisionPoker.dmg",
    "windows": "https://github.com/user/repo/releases/latest/download/VisionPokerSetup.exe",
}
```

## Troubleshooting

### macOS: "App is damaged and can't be opened"

The app wasn't properly signed/notarized:

```bash
# User workaround (not recommended for production)
xattr -cr /Applications/Vision\ Poker.app
```

Solution: Properly sign and notarize the app.

### Windows: "Windows protected your PC"

SmartScreen warning for unsigned apps:

Solution: Sign the app with a code signing certificate.

### App crashes on startup

Check for missing dependencies:

```bash
# macOS
dist/Vision\ Poker.app/Contents/MacOS/Vision\ Poker

# Windows (run from command prompt)
VisionPoker.exe
```

### PyInstaller: Module not found

Add hidden imports:

```bash
pyinstaller --hidden-import "missing_module" app.py
```
