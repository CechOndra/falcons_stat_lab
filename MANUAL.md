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

The **Logged** column grades how completely each game is tracked:

- **Basic** (the minimum for trustworthy stats): shots and line changes
  (ice time) are logged.
- **Premium**: Basic, plus every event fully filled in — no pending markers,
  every shot with its location and shooter.
- Small icons mark optional extras present in that game: ◉ faceoffs,
  ⇥ zone entries, ⇤ zone exits. Hover the badge for details.

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

| `F` | faceoff (won/lost, optional taker) |
| `E` | zone entry — into the offensive zone |
| `W` | zone exit — breakout from our zone |

Plus `N` = **quick marker**: instantly stamps the current game + video time
with no panel and no pause (see 3.5).

To rebind any shortcut: **Setup tab → Keyboard shortcuts → Rebind**, then
press the new key. Stored per browser; one click resets the defaults.

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
accordingly). The faint dashed area in front of the net is the **slot**
("home plate"); shots inside it are tagged automatically for the slot stats.
For our shots the shooter number is required. Result: on goal / missed /
blocked / goal. If an opponent shot was **blocked by one of our players**,
enter the blocker's number (our blocked shots don't track the opposing
blocker). For shots on goal and goals you can optionally click the goal-mouth
diagram (shooter's view; the translucent goalie silhouette shows where the
pads, glove and blocker are) to record placement — that click is what powers
xGOT.

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

**Lines (once per game, editable any time)** — in the Log tab click **Edit
lines** (next to the on-ice display) and assign each dressed player to F1–F4 /
D1–D3 / **G** (the goalie in net). Players you leave unassigned become
**extras** — spare skaters, dual F/D players, anyone who floats between lines.
When the coach shuffles lines mid-game, reopen the editor and adjust; it takes
effect from the next snapshot.

**Line change (`L`)** — opens the on-ice panel showing your lines as rows of
player buttons (highlighted = currently on ice):

- **Click a player** to toggle him on/off — partial changes, extras jumping in
  for a regular, anything.
- **Click a line button** (F1…D3) to swap the whole unit: it benches the other
  F-lines (or D-pairs) and puts that line on. **Extras are never auto-removed**
  — if the spare F is playing instead of a 4th-liner, he stays through line
  swaps until you toggle him off yourself.
- **The goalie is automatic**: the player marked G is included in every saved
  snapshot without you touching him. The goalie row has a **pull/return**
  button for delayed penalties and late-game 6-on-5 (pulled = he's off, and
  you toggle the extra attacker on like any player); switch goalies via Edit
  lines.
- Keyboard-only alternative — everything also works as typed tokens in the
  input, each followed by Enter: a jersey number toggles that player,
  `f1`–`f4`/`d1`–`d3` swaps that line, `g` pulls/returns the goalie, `c`
  clears the skaters. **Enter on the empty field saves** the snapshot. A clean
  full change is `L`, `f2`, `d1`, Enter.

Ice time accrues between snapshots **only while the game clock runs**, so
stoppage time never inflates TOI. Log a snapshot at every change you care
about; more snapshots = more accurate TOI, on-ice and together stats.

**Optional extras — faceoffs (`F`), zone entries (`E`), zone exits (`W`)** —
entirely skippable stat families; track them in the games where you want the
extra depth. Faceoff: who won (us/opponent) and optionally which of our
players took it → faceoff % per team and player. Entry/exit: optionally the
player, plus controlled (carried/passed) vs uncontrolled (dump/chip) → zone
play counts and control rates. Games that contain these events get a small
icon in the games list (◉ faceoffs, ⇥ entries, ⇤ exits) so you can see at a
glance which games carry which stats.

**Quick logging (per-event, Setup → Quick logging)** — any loggable event
type can be switched to "quick by default": pressing its key then saves an
instant stub (type + game/video time, no panel, video keeps playing) instead
of opening the panel. Holding **Shift** with the key does the opposite of
the default — so with faceoffs set to quick, `F` stamps a stub and
`Shift+F` opens the full panel. Editing a stub (✎) opens its proper panel
directly, prefilled at the original time. **`Shift+K`** is the one-press
whistle: stops the game clock *and* drops a "whistle" marker (these don't
count as unfinished work). Every `K`/`Shift+K` press is also recorded
invisibly as clock history — that's what will drive video cutting and
replay-aware highlight clips later.

**Quick marker (`N`)** — for when something happened but you don't want to
stop: one keypress stamps the game time and video time, nothing else, and the
video keeps playing. Later, click ✎ on the marker to add a note ("faceoff",
"rewatch this") or **convert it into a real event** — the shot/goal/penalty/
lineup panel opens prefilled at the marker's original time. The event log
header shows a **complete/total counter**, and the filter next to it
("Needs info") lists exactly the events still missing details: markers, and
shots without a location or shooter. That's your second-pass worklist.

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
- **Team table**: attempts vs on-goal, xG and xGOT for/against, slot SOG
  (home plate), shots per PP, penalties by zone, PIM.
- **Shots by period**: for/against bars per period.
- **Player table**: G/A/P, SOG, shooting %, xG, blocks, penalties/PIM, screen
  credits, TOI total and split by 5v5/PP/PK, points per 60, 5v5 shots per 60,
  and on-ice shot/goal counts (for/against while the player was on the ice —
  the plus-minus / Corsi building blocks).
- **Together on ice**: TOI, GF/GA **and GF-per-60 / GA-per-60 rates** for
  your **defined line units** and for **player pairs** by shared ice time —
  line chemistry straight from the lineup snapshots, no extra logging. Pick
  a player in the selector to list *all* of their teammates sorted by time
  shared.
- **Shift chart**: select exactly one game in the filters and every player's
  shifts draw as a timeline across the periods — who played when, hover a
  bar for exact times.
- **Faceoffs & zone play**: team faceoff W-L-%, entries/exits with control
  rates, and a per-player table (appears once you log those event types).
- **Shot map**: dots colored by result (hover any dot for shooter, state,
  xG) or a density view; filter by team, player, result. All shots are shown
  attacking right.
- **Goal-mouth chart**: where on-goal shots went (shooter's view) — green =
  goals, blue = **saved**; the translucent goalie shows what was covered;
  hover any dot for its xG/xGOT.
- **⬇ CSV** on any table downloads it.

### Rink coordinates, zones and the slot

Shots are stored as **x/y in feet on a standard 200 × 85 ft rink**, always
normalized so the shooter attacks the right net. The diagram is drawn at the
true aspect ratio, so nothing is distorted. Reference points:

- net center **(189, 42.5)**, posts at y 39.5 / 45.5; goal lines x = 11 / 189
- blue lines x = 75 / 125 → offensive zone = x ∈ [125, 200]
- face-off dots (169, 20.5) and (169, 64.5); circles r = 15
- **slot ("home plate")**: the polygon (189, 39.5) → (169, 20.5) →
  (154, 20.5) → (154, 64.5) → (169, 64.5) → (189, 45.5) — from the posts out
  to the dots, then across the top of the circles. It's drawn faintly on
  every rink diagram, and each shot gets an automatic in-slot tag (team
  table: "Slot SOG"; shot-map tooltips).

**Everything you actually see is in meters.** Feet are only the internal
grid; each shot's distance to the net is shown in meters in the tooltips and
drives the shot-map distance filter (0–5 / 5–10 / 10–18 / 18+ m). For
orientation: the diagram is a 61 × 26 m rink (NHL proportions), net 3.4 m
from the end boards, blue lines ~22.9 m in, face-off dots ~6.1 m out from
the goal line, slot reaching ~10.7 m. If your rink is the wider European
30 m, clicks are proportional so heat maps stay right; absolute distances
near the side boards run slightly short — treat the meter values as
approximate.

### The xG and xGOT models (assumptions & sources)

**xG** — every located shot attempt gets
`xG = 1 / (1 + e^−(−0.895 − 0.050·distance_ft − 1.355·angle_rad))`,
a logistic model least-squares fitted to published NHL location values:
league shooting % on goal ≈ 7.2 % (2022-23), crease ≈ 15-25 %, slot 10-15 %,
perimeter 2-4 %, slot defined as 15-30 ft / 20-40°. Resulting anchors:
crease ≈ .20, mid-slot ≈ .10, circles ≈ .04, blue line ≈ .02.

**xGOT** (expected goals on target) — only for shots **on goal with a
recorded goal-mouth placement**:
`xGOT = P(goal | on goal, location) × placement factor`, where the base is a
second logistic fitted to on-goal anchors (crease .25, slot .13, circles
.055, point .025) and the placement factor rewards corners and the upper
net and penalizes the goalie's center mass, with a mild five-hole bump —
directions taken from published shot-target studies (low-center is the worst
target; high corners and five-hole outperform). Read it as: xGOT ≫ goals =
the goalie bailed them out / great placement wasted; goals ≫ xGOT on-target =
finishing above the shot quality.

Honesty note: these are NHL-derived numbers applied to an amateur league —
levels will differ (expect more goals than xG predicts), but rankings and
comparisons stay meaningful. Neither model knows about rebounds, rushes or
screens. Both live as two small functions in `app.py` (`xg_value`,
`xgot_value`); swap them and every stat updates. Sources: Zach Stafiej's NHL
22-23 SOG analysis (league sh% 7.19 %, crease ≈ 15 %), Ivy Hockey's shot
quality primer (slot 10-15 %, perimeter 2-4 %), MetricGate xG methodology
(logistic distance+angle form), Arctic Ice Hockey / The Point shot-target
placement studies.

## 5. Cutting the video & goal highlights

The clock history you produce with `C`, `K` and `Shift+K` doubles as a video
cut list. In the Log tab, the **Video exports** card generates ffmpeg scripts
(pick Windows `.bat` or macOS/Linux `.sh`):

- **Cut script** — removes everything where the game clock was stopped
  (intermissions, stoppages, delays), keeping 3 s of padding around each
  play segment, and joins the rest into `<video>_cut.mp4`.
- **Goal highlights script** — one clip per goal, from 20 s before the goal
  until the moment play resumed (your next clock start), so the celebration
  and the TV replay are included; if no resume was logged, 40 s after the
  goal.

Requirements and caveats:

- **ffmpeg** must be installed (`winget install ffmpeg` on Windows,
  `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Linux).
- Save the script **into the folder with the video file(s)** and run it. It
  uses stream copy: fast (a 2 h game cuts in a couple of minutes), zero
  quality loss, but cut points snap to the video's keyframes, so each edge
  can be off by a second or two.
- **Keep the original file.** Logged events point at timestamps in the
  original; the cut file is for watching and sharing, not for logging.
- The quality of the cuts equals the quality of your `K` discipline — if you
  skipped marking some stoppages, that dead time simply stays in.

## 6. Users & roles

The schema already carries admin / coach / player roles for the future
multi-user deployment; the local app runs as the seeded admin with no login.

## 7. Tips for a smooth logging session

- Calibrate (`C`) at the start of each period, and any time you seek around.
- Log the starting lineup (`L`) right after the opening face-off.
- Don't chase perfection live: log the required fields fast, then use the
  event log + video jump to enrich or fix events afterwards.
- Slow the video (`,`) for busy sequences, speed it up (`.`) between whistles.
