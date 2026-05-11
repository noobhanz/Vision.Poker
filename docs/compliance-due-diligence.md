# Compliance Due Diligence Note

Vision Poker should complete a formal compliance review before public release, paid distribution, or use on real-money poker sites.

## Purpose

The product reads a visible poker table from the screen and presents poker metrics in a HUD. Even though the app is designed to be read-only and does not click buttons, scrape hand histories, inject into clients, or communicate with poker servers, real-time assistance tools may still violate poker site rules or terms of service.

## Required Due Diligence

- Review the current terms of service, prohibited software policies, and third-party tool rules for each supported poker site.
- Confirm whether real-time equity, pot odds, EV, draw detection, or recommendations are allowed during active play.
- Confirm whether a screen-reading HUD is treated differently from a solver, tracker, hand-history tool, or automated assistant.
- Document site-by-site restrictions for PokerStars, GGPoker, PartyPoker, 888poker, WPT Global, and any future supported client.
- Get legal/compliance input before marketing, charging for, or distributing the app.
- Maintain a clear product boundary: no automated actions, no process injection, no memory reading, no server communication with poker clients, and no hand-history scraping unless explicitly confirmed as allowed.
- Add user-facing warnings where needed, especially if the tool is intended for study, replay, or research rather than live real-money play.

## Launch Gate

Do not ship a paid or public release until the compliance review is complete and documented. If site rules are unclear, default to the conservative interpretation and restrict usage to permitted contexts such as offline review, play-money environments, private testing, or training material.

This note is not legal advice. It is an internal product requirement to ensure the team performs proper due diligence before release.
