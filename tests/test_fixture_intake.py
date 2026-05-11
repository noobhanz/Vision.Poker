from pathlib import Path

from tools.fixture_intake import (
    build_manifest,
    import_fixtures,
    next_fixture_index,
    summarize_fixtures,
)


def _write_image(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def test_next_fixture_index_uses_existing_numeric_suffixes(tmp_path):
    _write_image(tmp_path / "pokerstars_001.png", b"a")
    _write_image(tmp_path / "pokerstars_009.png", b"b")
    _write_image(tmp_path / "other_099.png", b"c")

    assert next_fixture_index(tmp_path, "pokerstars") == 10


def test_import_fixtures_skips_duplicate_content(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    _write_image(dest / "pokerstars_001.png", b"same")
    _write_image(source / "new_a.png", b"same")
    _write_image(source / "new_b.png", b"different")

    imported, skipped = import_fixtures(source, dest, "pokerstars")

    assert [entry.filename for entry in imported] == ["pokerstars_002.png"]
    assert skipped == [
        {
            "source": str(source / "new_a.png"),
            "reason": "duplicate",
            "existing": "pokerstars_001.png",
        }
    ]
    assert (dest / "pokerstars_002.png").read_bytes() == b"different"


def test_dry_run_import_deduplicates_within_source(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()

    _write_image(source / "new_a.png", b"same")
    _write_image(source / "new_b.png", b"same")

    imported, skipped = import_fixtures(source, dest, "pokerstars", dry_run=True)

    assert [entry.filename for entry in imported] == ["pokerstars_001.png"]
    assert skipped == [
        {
            "source": str(source / "new_b.png"),
            "reason": "duplicate",
            "existing": "pokerstars_001.png",
        }
    ]
    assert not dest.exists()


def test_manifest_reports_annotation_status(tmp_path):
    _write_image(tmp_path / "pokerstars_001.png", b"a")
    (tmp_path / "pokerstars_001.json").write_text("{}")
    _write_image(tmp_path / "pokerstars_002.png", b"b")

    entries = summarize_fixtures(tmp_path)
    manifest = build_manifest(tmp_path)

    assert [entry.annotated for entry in entries] == [True, False]
    assert manifest["counts"]["total_images"] == 2
    assert manifest["counts"]["annotated"] == 1
    assert manifest["counts"]["reference_only"] == 1
    assert manifest["needs_annotation"] == ["pokerstars_002.png"]
