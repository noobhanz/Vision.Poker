# Live 4 Recording Analysis

Input folder:

`/Users/antonhorning/Desktop/PokerStars Screenshots/Live 4`

Recordings analyzed:

- `Screen Recording 2026-05-18 at 15.10.43.mov`
- `Screen Recording 2026-05-18 at 15.13.11.mov`
- `Screen Recording 2026-05-18 at 15.16.22.mov`
- `Screen Recording 2026-05-18 at 15.17.09.mov`
- `Screen Recording 2026-05-18 at 15.17.56.mov`
- `Screen Recording 2026-05-18 at 15.20.14.mov`

Frames were extracted at 2 FPS into `/private/tmp/pokerscanner-live4`.

## Summary

Live 4 contains both no-active-hero recordings and active hero-hand recordings. The active clips exposed two useful gaps:

- Missing live card templates for hands and boards on the `1906x1372` capture size.
- Pot OCR preprocessing that treated scaled pot labels as action-button regions.

Both issues were addressed in this pass.

## Final Report Totals

After adding targeted card templates and improving pot OCR:

| Clip | Frames | Active | OK | No Active Hero | Published OK | Main Remaining Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `15.10.43` | 277 | 0 | 0 | 276 | 0 | 1 incomplete hero frame |
| `15.13.11` | 252 | 0 | 0 | 252 | 0 | none |
| `15.16.22` | 56 | 0 | 0 | 56 | 0 | none |
| `15.17.09` | 54 | 25 | 25 | 28 | 24 | 1 incomplete hero frame |
| `15.17.56` | 263 | 158 | 134 | 42 | 100 | duplicate cards, partial boards |
| `15.20.14` | 185 | 155 | 144 | 18 | 125 | partial boards, duplicate cards |

Suspicious published OK count is 0 for the final reports.

## Fixes From Live 4

- Added targeted Live 4 card templates for confirmed misreads:
  - Hero cards: `Kh`, `8h`, `Jh`, `Jc`, `5s`, `3c`.
  - Board cards: `Jc`, `5c`, `5h`, `7h`, `Qs`, `As`.
- Adjusted pot OCR preprocessing so scaled pot-label regions are cropped as pot labels, not action buttons.
- Added OCR cleanup for PokerStars label/currency glyph noise such as `90.8007`.
- Raised the live report suspicious-money threshold from `$10` to `$50` to avoid false positives on legitimate deep stacks while still catching obvious OCR blowups.

## Remaining Work

The next reliability work is still board-card coverage and validation:

- Add more board templates from duplicate-card and partial-board samples.
- Convert selected Live 4 frames into labeled fixtures.
- Add field-level expected-state validation so `OK` means card, pot, stack, and action fields are all correct.
- Keep conservative publication rules for partial boards and duplicate-card states.
