# Card Reading Strategy

Vision.Poker should not depend on collecting exact full-card templates for every card, table size, theme, and poker client. That approach does not scale and causes live failures when a card such as `4s`, `Qd`, or `9s` is missing from the template library.

## Target Architecture

1. Locate the selected table window and scale the configured slot regions.
2. Inside each slot, locate the visible white card surface.
3. Normalize that card surface to a stable crop before recognition.
4. Read the rank and suit corner glyphs separately.
5. Accept a card only when rank and suit confidence are strong enough.
6. Use full-card templates only as fallback, diagnostics, or bootstrap data.
7. Hold the previous stable state through transient unreadable frames instead of guessing.

## Why This Scales

Full-card matching requires up to 52 exact templates per client and can still break across sizes or themes. Rank/suit recognition needs a smaller visual vocabulary: 13 ranks and 4 suits per visual family. For a new poker client, we should calibrate table geometry and gather a small rank/suit sample set, not rebuild every card at every size.

## Current Bottlenecks

- Full-card template coverage is incomplete, so missing cards can be misread as visually similar known cards.
- Rank/suit matching exists, but real PokerStars corner glyphs still score too weakly after normalization.
- Hero cards can be partially covered by the player badge, so the recognizer must use the visible top card area safely.
- The HUD must never publish a confident-looking card state from an ambiguous read.

## Next Build Step

Build and gate a production rank/suit recognizer:

- create a labeled corner-glyph fixture set from recordings,
- compare normalized rank/suit accuracy independently from full-card matching,
- require per-slot confidence and margin thresholds,
- keep full-card fallback conservative,
- report live-readiness as frame-level accuracy and stability, not just whether the HUD displays numbers.

If template matching remains fragile after normalized glyph extraction, train a tiny rank classifier and suit classifier from the labeled glyph crops. That is still far more scalable than per-card full-image templates.
