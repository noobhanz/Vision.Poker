# PokerStars Fixture Batch

These screenshots were copied from `/Users/antonhorning/Desktop/PokerStars Screenshots` and renamed to stable fixture names.

Frames with visible, reliably parsed VantaBlue hole cards have sidecar JSON files. Frames without visible hero cards, or with known overlay/card occlusion issues, are kept as visual references but are not strict parser fixtures yet because the current pipeline requires hero cards before it can create a `GameState`.

The sidecar JSON currently asserts card identity, board cards, pot size, hero stack, street, action mode, and visible red-button actions where available. Checkbox-only pre-action prompts are recognized as `preselect`; they do not produce betting recommendations.

`tools.replay_test` prints per-field accuracy for annotated fixtures. Unannotated screenshots remain useful visual references, but they are excluded from the accuracy denominator.

Street distribution in the screenshot batch:

- Preflop/no-board screenshots: 9 total (`pokerstars_001`, `005`, `006`, `008`, `009`, `017`, `019`, `020`, `021`)
- Strict preflop annotations currently passing: 9
- Flop screenshots: 4 total (`pokerstars_002`, `007`, `010`, `018`)
- Turn screenshots: 4 total (`pokerstars_003`, `011`, `012`, `022`)
- River/showdown screenshots: 5 total (`pokerstars_004`, `013`, `014`, `015`, `016`)

Annotated frames:

- `pokerstars_001`: preflop, hero `2h 6s`
- `pokerstars_005`: preflop, hero `Qh 2c`
- `pokerstars_006`: preflop, hero `3d 6s`
- `pokerstars_008`: preflop, hero `Td Jd`
- `pokerstars_009`: preflop, hero `Td Jd`
- `pokerstars_010`: flop, hero `Td Jd`
- `pokerstars_011`: turn, hero `Td Jd`
- `pokerstars_012`: turn, hero `Td Jd`
- `pokerstars_013`: river, hero `Td Jd`
- `pokerstars_017`: preflop, hero `6h 5h`
- `pokerstars_018`: flop, hero `6h 5h`
- `pokerstars_019`: preflop, hero `Jc Js`
- `pokerstars_020`: preflop, hero `Jc Js`
- `pokerstars_021`: preflop all-in/showdown, hero `Jd Js`
- `pokerstars_022`: turn all-in/showdown, hero `Jc Js`

Unannotated reference frames:

- `pokerstars_002` through `pokerstars_004`
- `pokerstars_007`
- `pokerstars_014` through `pokerstars_016`
