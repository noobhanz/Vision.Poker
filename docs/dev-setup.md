# Development Setup

This guide keeps the default workflow offline: use saved screenshots first, then only run live capture when you explicitly want a smoke test against a visible poker table.

## Environment

Use Python 3.11 or newer. Python 3.12 is the current tested local version.

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS, live window discovery depends on `pyobjc-framework-Quartz`, and screen capture requires Screen Recording permission for the terminal or IDE that launches the app.

## Offline Checks

Run the normal unit test suite:

```bash
python -m pytest -q
```

Run the strict PokerStars screenshot replay batch:

```bash
python -m tools.replay_test \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash \
  --monte-carlo 100 \
  --strict
```

The replay summary reports expected fixture pass rate plus field-level accuracy for cards, board, pot, stack, street, and visible action controls. Reference-only screenshots without sidecar JSON are processed, but excluded from accuracy percentages.

## Fixture Intake

Summarize the current PokerStars fixture set:

```bash
python -m tools.fixture_intake \
  --dest tests/fixtures/sample_frames/pokerstars
```

Import a new screenshot batch with stable names and duplicate detection:

```bash
python -m tools.fixture_intake \
  --input "/Users/antonhorning/Desktop/PokerStars Screenshots" \
  --dest tests/fixtures/sample_frames/pokerstars \
  --prefix pokerstars \
  --manifest tests/fixtures/sample_frames/pokerstars/fixture_manifest.json
```

Use `--dry-run` first when checking a large batch. Imported screenshots without sidecar JSON are marked `reference-only` until they are annotated.

Run one screenshot, useful when fixing a specific fixture:

```bash
python -m tools.replay_test \
  --input tests/fixtures/sample_frames/pokerstars/pokerstars_020.png \
  --skin pokerstars_mac_cash \
  --monte-carlo 20 \
  --strict
```

Render an annotated debug image:

```bash
python -m tools.debug_frame \
  --input tests/fixtures/sample_frames/pokerstars/pokerstars_020.png \
  --skin pokerstars_mac_cash \
  --output /tmp/pokerstars_020_debug.png
```

## Template Refresh

If fixture annotations change, regenerate card and numeric OCR templates from the annotated screenshots:

```bash
python -m tools.extract_templates \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash \
  --output vision/templates \
  --overwrite

python -m tools.extract_ocr_templates \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash \
  --output vision/templates/ocr
```

After regenerating templates, rerun the strict replay batch and `pytest`.

## Optional Live Smoke Test

Only run this when a PokerStars table is visible and you want to validate the capture path:

```bash
python -m tools.live_read_once \
  --title PokerStars \
  --skin pokerstars_mac_cash \
  --json \
  --debug-output /tmp/live_debug.png
```

If the capture returns a desktop background, a blank frame, or the wrong window, grant macOS Screen Recording permission to the launching app, restart that app, and retry.

## Compliance Boundary

Before public release, paid distribution, or real-money live use, complete the compliance review in `docs/compliance-due-diligence.md`. Until that review is complete, treat live capture as a developer smoke test and use offline screenshots for normal validation.
