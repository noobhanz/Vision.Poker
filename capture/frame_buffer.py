"""
Only emit a frame downstream if the game state regions have changed.
Compare perceptual hash (pHash) of ROI regions between frames.
Avoids redundant equity computation when nothing has changed.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import imagehash
    from PIL import Image

    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


@dataclass
class ROI:
    """Region of interest within a frame."""

    x: int
    y: int
    width: int
    height: int
    name: str = ""

    def extract(self, frame: np.ndarray) -> np.ndarray:
        """Extract this ROI from a frame."""
        return frame[self.y : self.y + self.height, self.x : self.x + self.width]


class FrameBuffer:
    """
    Buffer that only passes through frames when ROI regions have changed.
    Uses perceptual hashing (pHash) to detect changes.
    """

    def __init__(
        self,
        roi_regions: list[ROI],
        hash_threshold: int = 8,
    ):
        """
        Initialize frame buffer.

        Args:
            roi_regions: List of ROIs to monitor for changes
            hash_threshold: Max Hamming distance to consider "same" (0-64)
                          Lower = more sensitive, higher = more tolerant
        """
        self.roi_regions = roi_regions
        self.hash_threshold = hash_threshold
        self._last_hashes: dict[str, Optional["imagehash.ImageHash"]] = {}
        self._frame_count = 0

    def _compute_phash(self, region: np.ndarray) -> Optional["imagehash.ImageHash"]:
        """Compute perceptual hash of an image region."""
        if not IMAGEHASH_AVAILABLE:
            return None

        try:
            # Convert numpy array to PIL Image
            img = Image.fromarray(region)
            return imagehash.phash(img)
        except Exception:
            return None

    def _region_changed(self, roi: ROI, frame: np.ndarray) -> bool:
        """Check if a specific ROI has changed since last frame."""
        try:
            region = roi.extract(frame)
        except (IndexError, ValueError):
            # ROI out of bounds
            return True

        current_hash = self._compute_phash(region)
        if current_hash is None:
            # Can't compute hash, assume changed
            return True

        last_hash = self._last_hashes.get(roi.name)
        if last_hash is None:
            # First frame for this ROI
            self._last_hashes[roi.name] = current_hash
            return True

        # Compare hashes using Hamming distance
        distance = current_hash - last_hash
        changed = distance > self.hash_threshold

        if changed:
            self._last_hashes[roi.name] = current_hash

        return changed

    def has_changed(self, frame: np.ndarray) -> bool:
        """
        Check if any monitored ROI has changed since last frame.

        Args:
            frame: Current frame as np.ndarray (BGR)

        Returns:
            True if any ROI changed, False if all ROIs are the same
        """
        self._frame_count += 1

        # Always pass first frame
        if self._frame_count == 1:
            for roi in self.roi_regions:
                try:
                    region = roi.extract(frame)
                    self._last_hashes[roi.name] = self._compute_phash(region)
                except (IndexError, ValueError):
                    pass
            return True

        # Check if any ROI changed
        for roi in self.roi_regions:
            if self._region_changed(roi, frame):
                return True

        return False

    def reset(self) -> None:
        """Reset the buffer state."""
        self._last_hashes.clear()
        self._frame_count = 0


class SimpleFrameBuffer:
    """
    Simpler frame buffer using pixel difference instead of pHash.
    Faster but less robust to minor variations.
    """

    def __init__(
        self,
        roi_regions: list[ROI],
        pixel_threshold: float = 0.02,
    ):
        """
        Initialize simple frame buffer.

        Args:
            roi_regions: List of ROIs to monitor
            pixel_threshold: Fraction of pixels that must differ (0.0-1.0)
        """
        self.roi_regions = roi_regions
        self.pixel_threshold = pixel_threshold
        self._last_regions: dict[str, Optional[np.ndarray]] = {}

    def _region_changed(self, roi: ROI, frame: np.ndarray) -> bool:
        """Check if ROI pixels have changed significantly."""
        try:
            region = roi.extract(frame)
        except (IndexError, ValueError):
            return True

        last_region = self._last_regions.get(roi.name)
        if last_region is None:
            self._last_regions[roi.name] = region.copy()
            return True

        # Check shape match
        if region.shape != last_region.shape:
            self._last_regions[roi.name] = region.copy()
            return True

        # Calculate pixel difference
        diff = np.abs(region.astype(np.float32) - last_region.astype(np.float32))
        changed_pixels = np.sum(diff > 30)  # Pixels with >30 intensity change
        total_pixels = region.size
        change_ratio = changed_pixels / total_pixels

        if change_ratio > self.pixel_threshold:
            self._last_regions[roi.name] = region.copy()
            return True

        return False

    def has_changed(self, frame: np.ndarray) -> bool:
        """Check if any ROI has changed."""
        for roi in self.roi_regions:
            if self._region_changed(roi, frame):
                return True
        return False

    def reset(self) -> None:
        """Reset buffer state."""
        self._last_regions.clear()
