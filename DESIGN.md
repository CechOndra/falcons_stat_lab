# DESIGN.md

Visual system for Falcons Stat Lab. All tokens live as CSS custom properties
in the `<style>` block of `static/index.html` (`:root` light, overridden in
`@media (prefers-color-scheme: dark)`). Chart colors follow the validated
data-viz palette (see the dataviz skill reference); UI chrome shares the same
neutrals.

## Color tokens

| Token | Role | Light | Dark |
|---|---|---|---|
| `--page` | page plane | `#f9f9f7` | `#0d0d0d` |
| `--surface` | cards, controls | `#fcfcfb` | `#1a1a19` |
| `--ink` | primary text | `#0b0b0b` | `#ffffff` |
| `--ink2` | secondary text | `#52514e` | `#c3c2b7` |
| `--ink3` | hints, table headers (AA at 12px) | `#6f6e69` | `#a5a49c` |
| `--muted` | chart axis labels only | `#898781` | `#898781` |
| `--grid` | hairlines, gridlines | `#e1e0d9` | `#2c2c2a` |
| `--axis` | control borders, chart baselines | `#c3c2b7` | `#383835` |
| `--border` | card hairline ring | `rgba(11,11,11,.10)` | `rgba(255,255,255,.10)` |
| `--us` | accent / Falcons / "for" series | `#2a78d6` | `#3987e5` |
| `--opp` | opponent / "against" series | `#e34948` | `#e66767` |
| `--goal` `--miss` `--block` | shot-result series | `#008300` `#eda100` `#4a3aa7` | `#008300` `#c98500` `#9085e9` |

Rules: one accent (`--us`) for primary actions, selection, and "our team".
Result colors appear only on chart marks and legends. Gray text never sits on
a colored background.

## Typography

System stack: `system-ui, -apple-system, "Segoe UI", sans-serif` — one family
everywhere. Fixed rem scale (product register, ratio ≈1.2):

- body 14px/1.5 · table cells 13.5px · hints/labels 12px
- h2 17px/600 · h3 14px/650 · section labels 11px/600 uppercase +0.04em
- tile value 26px/700; all numeric columns `font-variant-numeric: tabular-nums`

## Spacing & radius

4px base scale (4/8/12/16/24). Cards 14–16px padding, radius 10px. Controls
radius 7px. Dialogs radius 12px. Nav and cards separated by hairlines, not
shadows (shadow reserved for open dialogs).

## Components

Buttons: default / `.pri` (accent) / `.ghost` (bare). All have hover wash
(4% ink mix), active (8%), `:focus-visible` 2px accent outline, disabled 50%.
Inputs/selects: accent border + soft ring on focus. Tables: uppercase spaced
header row in `--ink3`, hairline row separators, hover wash on interactive
rows. Empty tables show a one-line teaching hint, never blank space.

## Motion

150ms ease-out on background/border/color/box-shadow only. No layout
animation, no page-load choreography. `prefers-reduced-motion: reduce`
disables all transitions.
