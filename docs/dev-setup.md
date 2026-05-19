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

Extract ordered frames from a screen recording:

```bash
python -m tools.video_to_frames \
  --input "/Users/antonhorning/Desktop/PokerStars Screenshots/Live/Screen Recording.mov" \
  --output tests/fixtures/live_sequences/pokerstars_live_001 \
  --fps 2 \
  --prefix pokerstars_live_001
```

Create a compact live-regression scoreboard from an extracted sequence:

```bash
python -m tools.live_regression_report \
  --input tests/fixtures/live_sequences/pokerstars_live_001 \
  --skin pokerstars_mac_cash \
  --stable-frames 2 \
  --monte-carlo 20 \
  --output /tmp/pokerstars_live_regression_summary.json
```

Use this report as the live-readiness baseline. Track `published_ok`,
`published_warnings`, `suspicious_published_ok_count`, and the top warning
statuses before and after recognizer changes.

When investigating card-reader warnings, add `--include-card-diagnostics` to
include per-slot full-card and rank/suit candidates in the warning samples.

Run the live-readiness gate when you want a pass/fail check instead of a report:

```bash
python -m tools.live_readiness_gate \
  --input tests/fixtures/live_sequences/pokerstars_live_smoke \
  --skin pokerstars_mac_cash \
  --stable-frames 2 \
  --monte-carlo 20 \
  --max-published-warning-rate 0.25 \
  --min-published-ok 3 \
  --min-actionable-published-ok 2 \
  --required-published-streets preflop,flop,river
```

The repo includes a tiny smoke sequence at
`tests/fixtures/live_sequences/pokerstars_live_smoke`. It is intentionally only
large enough to cover stable preflop, flop, river/all-in, no-active, and
board-warning states without committing a full recording. It is not meant to
look like smooth playback; it will jump between a few sampled frames.

Replay an extracted sequence or short recording through the actual HUD:

```bash
python -m tools.replay_hud \
  --input tests/fixtures/live_sequences/pokerstars_live_smoke \
  --skin pokerstars_mac_cash \
  --fps 2
```

This opens a replay-table window and loops the sequence with a standalone
Vision Poker HUD panel beside it. Press `Ctrl+C` in the terminal to stop it,
or add `--once` to play through a sequence one time and exit. Add
`--table-overlay-hud` only when you want to inspect the older transparent
in-table overlay.

Run the same replay through the normal screen-capture path:

```bash
python -m tools.replay_hud \
  --input tests/fixtures/live_sequences/pokerstars_live_smoke \
  --skin pokerstars_mac_cash \
  --fps 2 \
  --screen-capture-replay
```

This is the closest offline mimic of live use: the tool displays the recorded
table in a borderless window, captures that visible window from the screen,
then updates the standalone HUD from the captured pixels. If this cannot find
or capture the replay window, check macOS Screen Recording permission for the
terminal or app that launched it.

For an actual screen recording, point `--input` at the `.mov` or `.mp4` file
and use a higher FPS so playback feels closer to live:

```bash
python -m tools.replay_hud \
  --input "/Users/antonhorning/Desktop/PokerStars Screenshots/Live/Screen Recording.mov" \
  --skin pokerstars_mac_cash \
  --fps 12 \
  --screen-capture-replay
```

If your recording filename differs, use the exact path from Finder. Passing a
folder of sparse extracted frames is useful for regression checks, but it will
not look like continuous play.

Use console mode when you want a deterministic, non-GUI smoke test:

```bash
python -m tools.replay_hud \
  --input tests/fixtures/live_sequences/pokerstars_live_smoke \
  --skin pokerstars_mac_cash \
  --fps 2 \
  --monte-carlo 20 \
  --no-hud
```

This mode intentionally bypasses live screen capture. It is the recommended
step before a real PokerStars smoke test because it exercises the parser,
stabilizer, metrics, and HUD update path from repeatable recorded pixels.

Bootstrap review-only candidate annotations for unannotated frames the parser can read:

```bash
python -m tools.bootstrap_annotations \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash
```

This writes `*.candidate.json` files. They are not loaded by strict replay; review them visually before promoting any candidate to a strict `.json` sidecar.

Run one screenshot, useful when fixing a specific fixture:

```bash
python -m tools.replay_test \
  --input tests/fixtures/sample_frames/pokerstars/pokerstars_020.png \
  --skin pokerstars_mac_cash \
  --monte-carlo 20 \
  --strict
```

Replay a sequence with the same consecutive-frame publish rule used by the
live HUD:

```bash
python -m tools.replay_test \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash \
  --monte-carlo 100 \
  --stable-frames 2
```

This is most useful with an ordered capture sequence where the same table state
appears across multiple changed frames. One-off fixture collections may show few
or no published states when `--stable-frames` is greater than 1.

Render an annotated debug image:

```bash
python -m tools.debug_frame \
  --input tests/fixtures/sample_frames/pokerstars/pokerstars_020.png \
  --skin pokerstars_mac_cash \
  --output /tmp/pokerstars_020_debug.png
```

Write per-slot card diagnostics with crops, top rank/suit guesses, confidence,
and accept/reject status:

```bash
python -m tools.card_slot_diagnostics \
  --input tests/fixtures/sample_frames/pokerstars \
  --skin pokerstars_mac_cash \
  --output /tmp/card_slot_diagnostics
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
