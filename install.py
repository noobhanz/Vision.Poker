#!/usr/bin/env python3
"""
vision.poker - One-Click Installer

This script handles the complete installation process:
1. Checks Python version
2. Creates virtual environment (if needed)
3. Installs dependencies
4. Launches the GUI wizard

Usage:
    python3 install.py

Or make executable and double-click:
    chmod +x install.py
    ./install.py
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


def print_banner():
    """Print welcome banner."""
    print()
    print("  ╔═══════════════════════════════════════╗")
    print("  ║                                       ║")
    print("  ║         VISION.POKER INSTALLER        ║")
    print("  ║                                       ║")
    print("  ╚═══════════════════════════════════════╝")
    print()


def check_python():
    """Check Python version."""
    print("Checking Python version...", end=" ")
    version = sys.version_info

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("[X]")
        print(f"\n  Error: Python 3.10+ required (you have {version.major}.{version.minor})")
        print("  Please install Python 3.10 or later from https://python.org")
        return False

    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def setup_venv():
    """Create and activate virtual environment."""
    project_dir = Path(__file__).parent
    venv_dir = project_dir / "venv"

    if not venv_dir.exists():
        print("Creating virtual environment...", end=" ")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
        )
        print("[OK]")

    # Get path to venv Python
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    return str(venv_python)


def install_dependencies(python_path):
    """Install required packages."""
    project_dir = Path(__file__).parent
    requirements = project_dir / "requirements.txt"

    print("Installing dependencies...")
    print("  (this may take a few minutes)")
    print()

    # Core packages first (for the installer GUI)
    core_packages = ["PyQt6"]

    for pkg in core_packages:
        print(f"  Installing {pkg}...", end=" ", flush=True)
        result = subprocess.run(
            [python_path, "-m", "pip", "install", "-q", pkg],
            capture_output=True,
        )
        if result.returncode == 0:
            print("[OK]")
        else:
            print("[!]")

    # Install all requirements
    print("  Installing remaining packages...", end=" ", flush=True)
    result = subprocess.run(
        [python_path, "-m", "pip", "install", "-q", "-r", str(requirements)],
        capture_output=True,
    )

    if result.returncode == 0:
        print("[OK]")
    else:
        print("[!]")
        print(f"  Warning: Some packages may have failed to install")

    print()
    return True


def launch_wizard(python_path):
    """Launch the GUI installation wizard."""
    project_dir = Path(__file__).parent
    wizard_path = project_dir / "installer" / "wizard.py"

    print("Launching installation wizard...")
    print()

    # Run the wizard
    subprocess.run([python_path, str(wizard_path)])


def main():
    """Main installer entry point."""
    print_banner()

    # Check Python
    if not check_python():
        input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        # Setup virtual environment
        python_path = setup_venv()

        # Install dependencies
        if not install_dependencies(python_path):
            input("\nPress Enter to exit...")
            sys.exit(1)

        # Launch wizard
        launch_wizard(python_path)

    except KeyboardInterrupt:
        print("\n\nInstallation cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
