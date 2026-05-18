# Live 3 Recording Analysis

Input folder:

`/Users/antonhorning/Desktop/PokerStars Screenshots/Live 3`

Recordings analyzed:

- `Screen Recording 2026-05-18 at 12.17.43.mov`
- `Screen Recording 2026-05-18 at 12.19.16.mov`
- `Screen Recording 2026-05-18 at 12.20.58.mov`

Frames were extracted at 2 FPS into `/private/tmp/pokerscanner-live3`.

## Summary

Live 3 is primarily a no-active-hero validation set. The sampled frames show folded or otherwise inactive hero-card states while board cards and other seats may still be visible.

The initial report exposed a parser-order issue: board-card duplicate misreads could override the more important no-active-hero state. The parser now returns `NO_ACTIVE_HERO_CARDS` before evaluating board-card duplicate validity when no hero hand is detected.

## Final Report Totals

After the parser-order fix:

| Clip | Frames | Status Counts | Published States |
| --- | ---: | --- | ---: |
| `12.17.43` | 159 | `NO_ACTIVE_HERO_CARDS: 159` | 0 |
| `12.19.16` | 144 | `NO_ACTIVE_HERO_CARDS: 144` | 0 |
| `12.20.58` | 102 | `NO_ACTIVE_HERO_CARDS: 102` | 0 |

## Interpretation

This is the correct conservative behavior for these clips. The parser should not publish recommendations when the hero has no active hand, even if board cards are visible and even if board-card recognition has template misses.

Live 3 should be kept as a regression set for:

- Folded/no-active hero states.
- Board-only visible states.
- Preventing board-card errors from producing misleading active-hand statuses.

## Remaining Gap

Live 3 does not meaningfully cover active hero-card decision states. The next recordings still need active hands with visible hero cards, action buttons, and labeled ground truth so we can measure true field-level correctness.
