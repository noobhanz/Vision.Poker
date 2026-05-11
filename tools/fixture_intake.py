#!/usr/bin/env python3
"""Import and summarize screenshot fixtures.

Usage:
    python -m tools.fixture_intake --input "~/Desktop/PokerStars Screenshots"
    python -m tools.fixture_intake --dest tests/fixtures/sample_frames/pokerstars
"""

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass
class FixtureEntry:
    """One screenshot fixture record."""

    filename: str
    annotated: bool
    sha256: str
    source: Optional[str] = None


def sha256_file(path: Path) -> str:
    """Return a stable content hash for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_files(path: Path) -> list[Path]:
    """Return supported image files from a file or directory."""
    if path.is_file():
        return [path] if path.suffix.lower() in IMAGE_EXTENSIONS else []
    return sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
    )


def next_fixture_index(dest: Path, prefix: str) -> int:
    """Return the next numeric fixture suffix for a destination folder."""
    max_index = 0
    for path in image_files(dest) if dest.exists() else []:
        stem = path.stem
        if not stem.startswith(f"{prefix}_"):
            continue
        suffix = stem.removeprefix(f"{prefix}_")
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return max_index + 1


def existing_hashes(dest: Path) -> dict[str, Path]:
    """Map fixture content hashes to existing destination files."""
    hashes = {}
    if not dest.exists():
        return hashes
    for path in image_files(dest):
        hashes[sha256_file(path)] = path
    return hashes


def summarize_fixtures(dest: Path) -> list[FixtureEntry]:
    """Summarize existing fixtures and whether they have sidecar JSON."""
    entries = []
    if not dest.exists():
        return entries
    for path in image_files(dest):
        entries.append(
            FixtureEntry(
                filename=path.name,
                annotated=path.with_suffix(".json").exists()
                or path.with_suffix(".expected.json").exists(),
                sha256=sha256_file(path),
            )
        )
    return entries


def import_fixtures(
    source: Path,
    dest: Path,
    prefix: str,
    *,
    dry_run: bool = False,
) -> tuple[list[FixtureEntry], list[dict]]:
    """Copy new screenshot files into the destination using stable names."""
    imported = []
    skipped = []
    hashes = existing_hashes(dest)
    next_index = next_fixture_index(dest, prefix)

    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    for source_path in image_files(source):
        digest = sha256_file(source_path)
        if digest in hashes:
            skipped.append(
                {
                    "source": str(source_path),
                    "reason": "duplicate",
                    "existing": hashes[digest].name,
                }
            )
            continue

        target_name = f"{prefix}_{next_index:03d}{source_path.suffix.lower()}"
        target_path = dest / target_name
        next_index += 1

        if not dry_run:
            shutil.copy2(source_path, target_path)
        hashes[digest] = target_path

        imported.append(
            FixtureEntry(
                filename=target_name,
                annotated=False,
                sha256=digest,
                source=str(source_path),
            )
        )

    return imported, skipped


def build_manifest(
    dest: Path,
    *,
    imported: Optional[list[FixtureEntry]] = None,
    skipped: Optional[list[dict]] = None,
) -> dict:
    """Build a machine-readable fixture intake manifest."""
    entries = summarize_fixtures(dest)
    imported = imported or []
    skipped = skipped or []

    by_name = {entry.filename: entry for entry in entries}
    for entry in imported:
        by_name.setdefault(entry.filename, entry)

    all_entries = sorted(by_name.values(), key=lambda item: item.filename)
    annotated = [entry for entry in all_entries if entry.annotated]
    reference_only = [entry for entry in all_entries if not entry.annotated]

    return {
        "destination": str(dest),
        "counts": {
            "total_images": len(all_entries),
            "annotated": len(annotated),
            "reference_only": len(reference_only),
            "imported": len(imported),
            "skipped": len(skipped),
        },
        "needs_annotation": [entry.filename for entry in reference_only],
        "skipped": skipped,
        "entries": [
            {
                "filename": entry.filename,
                "annotated": entry.annotated,
                "sha256": entry.sha256,
                **({"source": entry.source} if entry.source else {}),
            }
            for entry in all_entries
        ],
    }


def print_manifest_summary(manifest: dict) -> None:
    """Print a compact human-readable manifest summary."""
    counts = manifest["counts"]
    print(f"Destination: {manifest['destination']}")
    print(f"Images: {counts['total_images']}")
    print(f"Annotated: {counts['annotated']}")
    print(f"Reference-only: {counts['reference_only']}")
    print(f"Imported: {counts['imported']}")
    print(f"Skipped: {counts['skipped']}")

    needs_annotation = manifest["needs_annotation"]
    if needs_annotation:
        print()
        print("Needs annotation:")
        for filename in needs_annotation:
            print(f"  {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and summarize screenshot fixtures")
    parser.add_argument(
        "--input",
        "-i",
        default=None,
        help="Optional screenshot file or directory to import",
    )
    parser.add_argument(
        "--dest",
        "-d",
        default="tests/fixtures/sample_frames/pokerstars",
        help="Fixture destination directory",
    )
    parser.add_argument(
        "--prefix",
        "-p",
        default="pokerstars",
        help="Stable fixture filename prefix",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        default=None,
        help="Optional JSON manifest path to write",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without copying or writing a manifest",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the manifest as JSON",
    )
    args = parser.parse_args()

    dest = Path(args.dest)
    imported: list[FixtureEntry] = []
    skipped: list[dict] = []

    if args.input:
        source = Path(args.input)
        if not source.exists():
            raise SystemExit(f"Input path not found: {source}")
        imported, skipped = import_fixtures(
            source,
            dest,
            args.prefix,
            dry_run=args.dry_run,
        )

    manifest = build_manifest(dest, imported=imported, skipped=skipped)

    if args.json:
        print(json.dumps(manifest, indent=2))
    else:
        print_manifest_summary(manifest)

    if args.manifest and not args.dry_run:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print()
        print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
