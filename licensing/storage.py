"""Local license storage and machine ID generation."""

import hashlib
import json
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Optional


def get_machine_id() -> str:
    """
    Generate a unique machine identifier.

    Uses platform-specific hardware identifiers to create a stable ID
    that persists across reboots but is unique to each machine.
    """
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Use hardware UUID
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    uuid_str = line.split('"')[-2]
                    return hashlib.sha256(uuid_str.encode()).hexdigest()[:32]

        elif system == "Windows":
            # Use machine GUID from registry
            result = subprocess.run(
                ["reg", "query", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "MachineGuid" in line:
                    guid = line.split()[-1]
                    return hashlib.sha256(guid.encode()).hexdigest()[:32]

        elif system == "Linux":
            # Use machine-id
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                machine_id = machine_id_path.read_text().strip()
                return hashlib.sha256(machine_id.encode()).hexdigest()[:32]

    except Exception:
        pass

    # Fallback: generate based on MAC address and hostname
    fallback = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(fallback.encode()).hexdigest()[:32]


class LicenseStorage:
    """
    Store and retrieve license information locally.

    License data is stored in the user's app data directory.
    """

    def __init__(self):
        self._storage_path = self._get_storage_path()
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_storage_path(self) -> Path:
        """Get platform-specific storage path."""
        system = platform.system()

        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "VisionPoker"
        elif system == "Windows":
            base = Path.home() / "AppData" / "Local" / "VisionPoker"
        else:
            base = Path.home() / ".config" / "visionpoker"

        return base / "license.json"

    def save_license(self, license_key: str) -> None:
        """Save license key to local storage."""
        data = {
            "license_key": license_key,
            "machine_id": get_machine_id(),
        }
        self._storage_path.write_text(json.dumps(data, indent=2))

    def load_license(self) -> Optional[str]:
        """Load license key from local storage."""
        if not self._storage_path.exists():
            return None

        try:
            data = json.loads(self._storage_path.read_text())
            return data.get("license_key")
        except (json.JSONDecodeError, KeyError):
            return None

    def clear_license(self) -> None:
        """Remove stored license."""
        if self._storage_path.exists():
            self._storage_path.unlink()

    @property
    def machine_id(self) -> str:
        """Get this machine's unique identifier."""
        return get_machine_id()
