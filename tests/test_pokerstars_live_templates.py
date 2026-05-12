from pathlib import Path

import cv2
import pytest

from vision.card_detector import CardDetector


LIVE_TEMPLATE_LABELS = ["Ac", "Ts", "2d", "6c", "2s", "6d", "Th", "8d"]


@pytest.mark.parametrize("card", LIVE_TEMPLATE_LABELS)
def test_live_template_variant_detects_itself(card):
    template_dir = Path("vision/templates")
    variants = sorted((template_dir / "cards").glob(f"{card}_pokerstars_live_*.png"))

    assert variants, f"missing live template variant for {card}"

    frame = cv2.imread(str(variants[0]))
    assert frame is not None

    detected = CardDetector(template_dir=template_dir).detect_template(
        frame,
        threshold=0.99,
    )

    assert any(detection.card == card for detection in detected)
