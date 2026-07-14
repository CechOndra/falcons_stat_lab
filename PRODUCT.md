# PRODUCT.md

## Register

**product** — app UI / tool. Design serves the task (logging events from game
video at speed, reading stats at a glance); the interface should disappear
into the workflow.

## Product

Falcons Stat Lab — local-first web app for logging and analyzing VŠE Falcons
Prague ice-hockey games from post-game video. FastAPI + SQLite backend, single
static HTML frontend, no build step.

## Users

- **The team statistician** (primary, today): logs a ~2 h game video across
  multiple sittings, keyboard-first, eyes on the video not the chrome.
- **Coach** (phase 2): view-only dashboards.
- **Players** (phase 2): their own stats.

## Job to be done

Log shots, goals, penalties and line changes without breaking video-watching
flow; afterwards, read trustworthy team/player statistics and maps.

## Brand personality

Focused · precise · calm. Sports-club pride without noise — Falcons blue as
the single accent on a quiet neutral surface.

## Anti-references

- SaaS landing gloss: gradients, glassmorphism, decorative motion.
- Dashboard-as-poster: hero numbers over substance.
- Anything that costs the logging loop a keystroke.

## Accessibility

Keyboard-first everything (mouse only for rink/goal-mouth clicks). WCAG AA
contrast in light and dark. Visible focus indicators. Reduced motion
respected. Tables as the always-available data view.

## Design principles

1. The video and the event log are the workspace — everything else recedes.
2. One accent (Falcons blue); status/result colors are reserved for meaning,
   never decoration.
3. Density is fine, ambiguity is not: tabular numerals, explicit labels.
4. Every interactive element has visible default/hover/focus/active states.
