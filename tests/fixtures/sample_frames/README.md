# Sample Frame Fixtures

Add real poker table screenshots here to drive the offline vision lab.

For each image, add a sidecar JSON file with the same basename:

```text
sample_001.png
sample_001.json
```

Expected JSON schema:

```json
{
  "hero_cards": ["Ah", "Kh"],
  "board_cards": ["2h", "7h", "Qs"],
  "pot_size": 100.0,
  "bet_to_call": 25.0,
  "hero_stack": 950.0,
  "street": "flop"
}
```

Run replay checks with:

```bash
python -m tools.replay_test --input tests/fixtures/sample_frames --skin pokerstars --debug-output debug_frames --strict
```

Render a single annotated debug image with:

```bash
python -m tools.debug_frame --input tests/fixtures/sample_frames/sample_001.png --skin pokerstars
```

Import a new screenshot batch with:

```bash
python -m tools.fixture_intake --input raw_screenshots --dest tests/fixtures/sample_frames/pokerstars --prefix pokerstars
```
