# Falcons Stat Lab — User Manual

Logging and analytics for VŠE Falcons Prague game videos. Everything runs on
your machine; the video never leaves your disk.

## 1. Setup

```
pip install -r requirements.txt
python app.py
```

Open **http://localhost:8000**. All data lives in one portable SQLite file,
`falcons.db`, next to `app.py` — back it up by copying that file.

First run seeds the season `2025/26` and the teams from
`seed/teams_template.csv`. Edit teams/seasons in the **Setup** tab.

### Roster

The league site blocks scraping, so the roster is yours to maintain (it's more
reliable that way anyway):

- **Roster** tab → add players one by one, or
- paste/upload a CSV: `number,name,position` (one player per line, header
  optional). Template: `seed/roster_template.csv`.

Every field is editable inline afterwards. "Active" controls who shows up when
creating a new game. Deleting a player keeps their already-logged events.

## 2. Creating games (including historical backfill)

**Games** tab → pick season, opponent (or type a new opponent name), date,
home/away, period length (20 min default), tick the dressed lineup → **Save
game**. Past games are created exactly the same way — just set the old date.
The score column fills itself from logged goals.

## 3. Logging a game

Open a game (**Games → Open / log**). Everything below happens in the **Log**
tab.

### 3.1 Video

Click the file picker and select the game video — one file, or several (one
per period). Files are streamed by the browser straight from disk, **nothing
is uploaded**. With multiple files, assign each to its period with the little
`P` selector and click a filename to switch.

When you re-open a game later, the app tells you *which* files it had and
where you stopped — browsers can't reopen local files by themselves, so
re-select the same file(s) and the video jumps back to your last position.

### 3.2 The game clock (calibration model)

The game clock is **independent of the video clock** — stoppages and
intermissions mean video time ≠ game time. The model is
*calibrate-then-toggle*:

1. Press **C**, enter the period and the time remaining exactly as the
   in-video score graphic shows, Enter. The clock now **runs**: it counts down
   in sync with video playback.
2. On a stoppage press **K** — the game clock freezes while the video plays
   on. When play resumes press **K** again — the clock continues from the
   frozen value, remapped to the current video position.
3. Whenever you notice drift (missed a stoppage, skipped around in the video),
   just press **C** and re-enter what the graphic shows. Calibration takes two
   seconds; do it liberally — at minimum at the start of every period.

Every event stores **both** the game time and the video timestamp, so clicking
an event in the log always jumps the video to the right moment even if your
calibration drifted afterwards.

### 3.3 Shortcut cheat sheet

| Key | Action |
|-----|--------|
| `Space` | play / pause video |
| `←` / `→` | seek −5 s / +5 s (`Shift` = ±1 s) |
| `,` / `.` | playback slower / faster |
| `C` | calibrate clock (period + time remaining) |
| `K` | game clock run / stop |
| `S` | shot by **us** |
| `A` | shot by opponent |
| `G` | **goal** by us |
| `H` | goal by opponent |
| `P` | penalty — us |
| `O` | penalty — opponent |
| `L` | line change (players on ice) |
| `U` | manual PP/PK state override |
| `Esc` | cancel any panel |
| `Enter` | next field / save panel |

To rebind, edit the `KEYS` map at the top of the script in
`static/index.html`.

### 3.4 Logging events

Triggering any event **auto-pauses** the video and opens a panel. After
saving, the video resumes automatically if the *"resume video after save"*
box is ticked (untick it to stay paused). The event's time is stamped at the
moment you pressed the shortcut, not when you finish the panel — take your
time filling it in.

Inside every panel: **Enter** moves to the next field, **Enter on the last
field saves**, **Esc cancels**. Selects respond to typed letters (`o`/`m`/`b`/`g`
for shot results, `o`/`n`/`d` for penalty zones). Players are always entered by
**jersey number** — the name appears next to the box so you can confirm.
Required fields block saving; optional ones are simply left empty.

**Shot (`S`/`A`)** — click the shot location on the rink (required; the
shooter always attacks the **right** net, regardless of team — click
accordingly). For our shots the shooter number is required. Result: on goal /
missed / blocked / goal. If an opponent shot was **blocked by one of our
players**, enter the blocker's number (our blocked shots don't track the
opposing blocker). For shots on goal and goals you can optionally click the
goal-mouth diagram (shooter's view) to record placement.

**Goal (`G`/`H`)** — same panel with result preset to GOAL. For our goals:
up to two assists, optional screen credit, optional net placement. Opponent
goals need only the location. Minor-penalty expiry on PP goals is handled
automatically in the stats.

**Penalty (`P`/`O`)** — ours: player number, length (2/5/10 — 10 counts PIM
but doesn't create a PK, it's a misconduct), zone where committed. Opponent:
length only. PP/PK situations are **derived automatically** from these,
including expiry, PP goals ending minors, coincidental minors (still counted
as even strength), and 5v3 (counted as one PP opportunity).

**State override (`U`)** — if the derived PP/PK state is wrong (missed
penalty, weird situation), force 5v5/PP/PK from the current game time onward;
choose *auto* to hand control back to the derivation.

**Line change (`L`)** — the fastest panel: type a jersey number, Enter —
toggles that player on/off the ice (chips show who's on). Repeat for each
change, then **Enter on the empty field saves** the new on-ice snapshot. `c`
clears everyone. The current six stay listed under the clock between changes.
Ice time accrues between snapshots **only while the game clock runs**, so
stoppage time never inflates TOI. Log a snapshot at every change you care
about; more snapshots = more accurate TOI and on-ice stats.

### 3.5 Fixing mistakes

The event log (right side, newest first) is fully editable: **✎** reopens the
event's panel with its values, **✕** deletes it. Clicking a row jumps the
video to that moment — the fastest way to double-check a call.

### 3.6 Stopping and resuming a session

Everything saves to the database the instant you log it — there is no save
button and closing the browser mid-game loses nothing. Video position and
clock calibration autosave every few seconds. To resume: open the app, open
the game, re-select the video file(s) when prompted — you're exactly where
you left off.

## 4. Dashboard

Filters at the top: season, opponent, specific games (Ctrl-click for several;
none selected = all), home/away, game state (5v5/PP/PK), period. **State and
period filter the shot/goal counts and maps; TOI and PP%/PK% always cover the
whole selected games** (a "PP-only TOI" reading comes from the TOI PP column
instead).

- **Tiles**: score, shots on goal, shooting %, PP % (goals per opportunity),
  PK % (kills per shorthanded situation), xG for/against.
- **Team table**: attempts vs on-goal, shots per PP, penalties by zone, PIM.
- **Shots by period**: for/against bars per period.
- **Player table**: G/A/P, SOG, shooting %, xG, blocks, penalties/PIM, screen
  credits, TOI total and split by 5v5/PP/PK, points per 60, 5v5 shots per 60,
  and on-ice shot/goal counts (for/against while the player was on the ice —
  the plus-minus / Corsi building blocks).
- **Shot map**: dots colored by result (hover any dot for shooter, state,
  xG) or a density view; filter by team, player, result. All shots are shown
  attacking right.
- **Goal-mouth chart**: where on-goal shots went, shooter's view; green =
  goals.
- **⬇ CSV** on any table downloads it.

### The xG model (assumptions)

Each located shot gets an expected-goal value from a simple logistic function
of **distance** and **angle off the net axis**:

```
xG = 1 / (1 + e^-(0.9 − 0.10·distance_ft − 1.3·angle_rad))
```

Hand-tuned for amateur hockey: ≈35 % point-blank in the slot, ≈5 % from the
face-off circles, ≈1 % from the blue line. It knows nothing about rebounds,
rushes, or screens — treat it as a location-quality index, not truth. The
whole model is the single `xg_value()` function in `app.py`; swap that
function to upgrade it, all stats pick it up automatically.

## 5. Users & roles

The schema already carries admin / coach / player roles for the future
multi-user deployment; the local app runs as the seeded admin with no login.

## 6. Tips for a smooth logging session

- Calibrate (`C`) at the start of each period, and any time you seek around.
- Log the starting lineup (`L`) right after the opening face-off.
- Don't chase perfection live: log the required fields fast, then use the
  event log + video jump to enrich or fix events afterwards.
- Slow the video (`,`) for busy sequences, speed it up (`.`) between whistles.
