#!/usr/bin/env python3
"""Create reviewable annotation candidates from parser output.

Candidate sidecars are intentionally named ``*.candidate.json`` so strict replay
does not load them. Review them visually before promoting any file to ``.json``.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from vision.card_detector import CardDetector
from vision.ocr_engine import OCREngine
from vision.roi_config import load_skin_config
from vision.state_parser import StateParser

from .fixture_intake import image_files
from .replay_test import load_expected, process_frame, state_to_dict


def candidate_path_for(frame_path: Path) -> Path:
    """Return the non-strict candidate sidecar path for an image."""
    return frame_path.with_suffix(".candidate.json")


def has_strict_annotation(frame_path: Path) -> bool:
    """Return whether replay already treats this frame as an expected fixture."""
    return load_expected(frame_path) is not None


def candidate_from_state(frame_name: str, state_dict: dict, status: str) -> dict:
    """Create a reviewable candidate annotation payload from parsed state."""
    payload = {
        "_candidate": {
            "image": frame_name,
            "source": "parser_bootstrap",
            "parse_status": status,
            "review_required": True,
        },
        "hero_cards": state_dict["hero_cards"],
        "board_cards": state_dict["board_cards"],
        "pot_size": state_dict["pot_size"],
        "hero_stack": state_dict["hero_stack"],
        "street": state_dict["street"],
        "action_mode": state_dict["action_mode"],
    }

    if state_dict.get("bet_to_call", 0) > 0 or state_dict.get("action_mode") == "decision":
        payload["bet_to_call"] = state_dict["bet_to_call"]
    if state_dict.get("legal_actions"):
        payload["legal_actions"] = state_dict["legal_actions"]
    if state_dict.get("action_amounts"):
        payload["action_amounts"] = state_dict["action_amounts"]

    return payload


def bootstrap_candidates(
    input_path: Path,
    skin: str,
    *,
    overwrite: bool = False,
    limit: Optional[int] = None,
) -> dict:
    """Parse unannotated screenshots and write candidate sidecars."""
    roi_config = load_skin_config(skin)
    state_parser = StateParser(CardDetector(), OCREngine())

    frame_files = image_files(input_path)
    written = []
    skipped = []
    failed = []

    for frame_path in frame_files:
        if limit is not None and len(written) >= limit:
            break

        if has_strict_annotation(frame_path):
            skipped.append({
                "file": frame_path.name,
                "reason": "strict_annotation_exists",
            })
            continue

        candidate_path = candidate_path_for(frame_path)
        if candidate_path.exists() and not overwrite:
            skipped.append({
                "file": frame_path.name,
                "reason": "candidate_exists",
            })
            continue

        state, _, status = process_frame(
            frame_path,
            state_parser,
            roi_config,
            monte_carlo_n=20,
        )

        if state is None:
            failed.append({
                "file": frame_path.name,
                "status": status,
            })
            continue

        candidate = candidate_from_state(frame_path.name, state_to_dict(state), status)
        with candidate_path.open("w") as f:
            json.dump(candidate, f, indent=2)
            f.write("\n")

        written.append({
            "file": frame_path.name,
            "candidate": candidate_path.name,
            "status": status,
            "street": candidate["street"],
            "hero_cards": candidate["hero_cards"],
            "board_cards": candidate["board_cards"],
        })

    return {
        "input": str(input_path),
        "skin": skin,
        "counts": {
            "written": len(written),
            "skipped": len(skipped),
            "failed": len(failed),
        },
        "written": written,
        "skipped": skipped,
        "failed": failed,
    }


def print_summary(summary: dict) -> None:
    """Print a compact candidate generation summary."""
    counts = summary["counts"]
    print(f"Input: {summary['input']}")
    print(f"Skin: {summary['skin']}")
    print(f"Written: {counts['written']}")
    print(f"Skipped: {counts['skipped']}")
    print(f"Failed: {counts['failed']}")

    if summary["written"]:
        print()
        print("Candidates:")
        for item in summary["written"]:
            board = " ".join(item["board_cards"]) if item["board_cards"] else "preflop"
            hero = " ".join(item["hero_cards"])
            print(f"  {item['candidate']}: {item['street']} hero={hero} board={board}")

    if summary["failed"]:
        print()
        print("Could not bootstrap:")
        for item in summary["failed"]:
            print(f"  {item['file']}: {item['status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap annotation candidates")
    parser.add_argument(
        "--input",
        "-i",
        default="tests/fixtures/sample_frames/pokerstars",
        help="Fixture image file or directory",
    )
    parser.add_argument(
        "--skin",
        "-s",
        default="pokerstars_mac_cash",
        help="Skin configuration to use",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .candidate.json files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidates to write",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        default=None,
        help="Optional JSON summary path to write",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input path not found: {input_path}")

    summary = bootstrap_candidates(
        input_path,
        args.skin,
        overwrite=args.overwrite,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_summary(summary)

    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w") as f:
            json.dump(summary, f, indent=2)
            f.write("\n")
        if not args.json:
            print()
            print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
