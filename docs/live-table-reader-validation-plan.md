# Live Table Reader Validation Plan

This plan covers the next work needed before trusting the PokerStars table reader in a more live environment. The goal is to move from "the parser often returns OK" to measured correctness against labeled recordings.

## Current Position

- The fixed-slot card matcher now normalizes live card ROIs before full-card template scoring.
- Live 2 recordings improved after adding confirmed card template variants.
- Remaining trust blockers are OCR/pot detection, partial or unreadable boards, duplicate-card edge cases, suspicious OK states, and unclear distinction between folded hero cards and no cards dealt yet.

## Guiding Rule

Do not treat an `OK` parse status as trustworthy until it is checked against expected truth. The next milestone is a labeled validation set with field-level accuracy for hero cards, board cards, pot, stack, action state, and no-card state.

## Step 1: Capture Targeted Short Recordings

Record 3-5 clips, each 1-2 minutes long. Keep the same supported setup unless intentionally testing a layout change:

- PokerStars macOS cash table.
- Same table size and visual theme.
- No window resizing during the clip.
- Prefer short clips with clear scenario coverage over long mixed recordings.

Required scenarios:

- Preflop hands with varied ranks and suits.
- Flop, turn, and river boards.
- Hero folded with no visible hero cards.
- No hero cards dealt yet while waiting for the next hand.
- Action pending: check, call, fold, bet/raise, and all-in where possible.
- Small pots and changing stack amounts.
- At least one hand where board cards are visible and action is available.

## Step 2: Write Minimal Ground Truth Notes

For each recording, create a short note with approximate timestamps. The note does not need to label every frame, but it should identify representative moments we can convert into fixtures.

For each moment, record:

- Timestamp.
- Hero cards, or `folded`, or `not_dealt_yet`.
- Board cards.
- Pot size.
- Bet or call amount.
- Hero stack.
- Visible legal action state.
- Any special state, such as all-in, waiting, hand ended, or animation in progress.

Example:

```text
00:12 hero=Kc 4d board=[] pot=0.03 call=0.02 stack=1.93 action=call/fold
00:31 hero=As 6s board=2h 9c Kh pot=0.06 call=0.00 stack=1.93 action=check
00:48 hero=folded board=Ac Tc 3s pot=0.05 action=none
01:05 hero=not_dealt_yet board=[] pot=0.00 action=waiting
```

## Step 3: Convert Recordings Into Labeled Fixtures

Extract frames from each clip at low FPS, then select representative frames from the ground truth notes.

For each selected frame:

- Save the image under `tests/fixtures/sample_frames/pokerstars/`.
- Save expected state beside it as JSON.
- Include the no-card state explicitly:
  - `hero_state: "active"` when two hero cards are visible.
  - `hero_state: "folded"` when the hero had cards and folded.
  - `hero_state: "not_dealt_yet"` when no cards have been dealt.
  - `hero_state: "unknown"` only when the screenshot cannot decide.

Expected JSON should cover:

- `hero_cards`
- `hero_state`
- `board_cards`
- `pot_size`
- `bet_to_call`
- `hero_stack`
- `legal_actions`
- `action_mode`
- `street`

## Step 4: Add Field-Level Validation

Extend the replay/report tooling so it compares parser output against expected JSON instead of only counting parse statuses.

Report these metrics separately:

- Hero card accuracy.
- Hero no-card state accuracy.
- Board card accuracy.
- Pot size accuracy.
- Bet-to-call accuracy.
- Hero stack accuracy.
- Action mode/legal action accuracy.
- False OK count.
- Low-confidence rejection count.

An `OK` frame should fail validation if any trusted field is wrong.

## Step 5: Fix Failures in Priority Order

Work failures in this order:

1. False OK states where wrong cards or wrong action data are published.
2. Hero no-card state confusion: folded versus not dealt yet.
3. Board card recognition failures.
4. Pot and bet OCR failures.
5. Stack OCR failures.
6. Ambiguous or animation frames that should be rejected instead of published.

Prefer conservative behavior. It is better to return a warning than to publish a confident but wrong recommendation.

## Step 6: Exit Criteria Before Live Trust

Do not move to a more live environment until the labeled validation set meets these minimums:

- Zero known false OK states in the validation set.
- Hero cards correct on active-hand frames.
- Folded versus not-dealt-yet states are explicitly classified or safely rejected.
- Board cards correct when visible and stable.
- Pot and bet values are either correct or marked unknown.
- HUD/recommendation output is suppressed when required fields are unknown or low confidence.

## Immediate Next Task

Capture the targeted short recordings and add ground truth notes. After that, build the labeled fixture comparison so every future parser change has a measurable pass/fail signal.
