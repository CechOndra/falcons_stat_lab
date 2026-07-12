#!/usr/bin/env python3
"""VSE Falcons Prague - hockey game stats logger & analytics.

Single-file backend: FastAPI + stdlib sqlite3. Run: python app.py -> http://localhost:8000
"""
import csv
import io
import json
import math
import os
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("FALCONS_DB", os.path.join(HERE, "falcons.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS seasons(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teams(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS players(
  id INTEGER PRIMARY KEY, number INTEGER, name TEXT NOT NULL,
  position TEXT DEFAULT '', photo TEXT DEFAULT '', active INTEGER DEFAULT 1);
-- roles are phase 2: schema ready, no auth wired yet
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','coach','player')),
  player_id INTEGER REFERENCES players(id));
CREATE TABLE IF NOT EXISTS games(
  id INTEGER PRIMARY KEY,
  season_id INTEGER REFERENCES seasons(id),
  opponent_id INTEGER REFERENCES teams(id),
  date TEXT DEFAULT '', home INTEGER DEFAULT 1,
  score_us INTEGER DEFAULT 0, score_opp INTEGER DEFAULT 0,
  period_len INTEGER DEFAULT 1200,
  roster TEXT DEFAULT '[]',      -- ponytail: JSON player-id list; join table when multi-team/auth lands
  lines TEXT DEFAULT '{}',       -- JSON {player_id: "F1".."F4"|"D1".."D3"|"G"}; unassigned = extras
  video_files TEXT DEFAULT '[]', -- JSON [{name,period}] - browsers can't reopen local files, names drive the re-select prompt
  last_video_pos REAL DEFAULT 0, last_video_idx INTEGER DEFAULT 0,
  calibration TEXT DEFAULT 'null',
  notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id),
  type TEXT NOT NULL CHECK(type IN ('shot','penalty','lineup','override','marker',
                                    'faceoff','entry','exit')),
  team TEXT DEFAULT 'us' CHECK(team IN ('us','opp')),
  period INTEGER NOT NULL,
  clock INTEGER NOT NULL,        -- seconds REMAINING in the period, as on the scoreboard
  video_ts REAL, video_idx INTEGER DEFAULT 0,
  player_id INTEGER, x REAL, y REAL,  -- feet on a 200x85 rink, shooter always attacks the RIGHT net (189, 42.5)
  result TEXT CHECK(result IN ('goal','on_goal','missed','blocked')),
  blocker_id INTEGER, assist1_id INTEGER, assist2_id INTEGER,
  net_x REAL, net_y REAL,        -- goal-mouth placement, percent of net width/height
  screen_id INTEGER,
  pim REAL, zone TEXT CHECK(zone IN ('off','neu','def')),
  on_ice TEXT,                   -- ponytail: JSON player-id list; join table if per-player SQL ever needed
  override TEXT,                 -- '5v5'|'pp'|'pk'|'auto' manual game-state override
  note TEXT DEFAULT '',          -- free text; markers use it ("faceoff", "check this")
  detail TEXT,                   -- entry/exit: 'controlled'|'uncontrolled'
  created_at TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS ev_game ON events(game_id);
"""

# writable columns per table (whitelist; keys are never interpolated from user input)
COLS = {
    "seasons": ["name"],
    "teams": ["name"],
    "players": ["number", "name", "position", "photo", "active"],
    "users": ["name", "role", "player_id"],
    "games": ["season_id", "opponent_id", "date", "home", "score_us", "score_opp",
              "period_len", "roster", "lines", "video_files", "last_video_pos",
              "last_video_idx", "calibration", "notes"],
    "events": ["game_id", "type", "team", "period", "clock", "video_ts", "video_idx",
               "player_id", "x", "y", "result", "blocker_id", "assist1_id",
               "assist2_id", "net_x", "net_y", "screen_id", "pim", "zone",
               "on_ice", "override", "note", "detail"],
}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def seed():
    con = db()
    con.executescript(SCHEMA)
    try:  # migration for DBs created before per-game lines existed
        con.execute("ALTER TABLE games ADD COLUMN lines TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass
    row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='events'").fetchone()
    if row and "'faceoff'" not in row["sql"]:  # rebuild events for newer event types/columns
        con.execute("PRAGMA foreign_keys=OFF")
        con.executescript("ALTER TABLE events RENAME TO events_old;" + SCHEMA)
        cols = ",".join(r[1] for r in con.execute("PRAGMA table_info(events_old)"))
        con.execute(f"INSERT INTO events({cols}) SELECT {cols} FROM events_old")
        con.execute("DROP TABLE events_old")
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
    if not con.execute("SELECT 1 FROM seasons LIMIT 1").fetchone():
        con.execute("INSERT INTO seasons(name) VALUES ('2025/26')")
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        con.execute("INSERT INTO users(name, role) VALUES ('Petr', 'admin')")
    if not con.execute("SELECT 1 FROM teams LIMIT 1").fetchone():
        path = os.path.join(HERE, "seed", "teams_template.csv")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    con.execute("INSERT OR IGNORE INTO teams(name) VALUES (?)",
                                (row["name"].strip(),))
    if not con.execute("SELECT 1 FROM players LIMIT 1").fetchone():
        # real names from the team lineup sheet; jersey numbers are placeholders
        path = os.path.join(HERE, "seed", "roster_template.csv")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if (row.get("name") or "").strip():
                        num = (row.get("number") or "").strip()
                        con.execute("INSERT INTO players(number,name,position) VALUES (?,?,?)",
                                    (int(num) if num.isdigit() else None,
                                     row["name"].strip(), (row.get("position") or "").strip()))
    con.commit()
    con.close()


app = FastAPI(title="Falcons Stat Lab")
seed()


# ------------------------------------------- specific routes (before /api/{table})

@app.post("/api/roster_csv")
async def roster_csv(request: Request):
    """Import roster from CSV text: number,name,position (header optional)."""
    text = (await request.body()).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if rows and rows[0] and rows[0][0].strip().lower() in ("number", "#", "cislo", "číslo"):
        rows = rows[1:]
    con = db()
    n = 0
    for r in rows:
        if len(r) < 2 or not r[1].strip():
            continue
        num = int(r[0]) if r[0].strip().isdigit() else None
        pos = r[2].strip() if len(r) > 2 else ""
        con.execute("INSERT INTO players(number,name,position) VALUES (?,?,?)",
                    (num, r[1].strip(), pos))
        n += 1
    con.commit()
    con.close()
    return {"imported": n}


@app.get("/api/game_flags")
def game_flags():
    """Per-game logging completeness: counts by event family + open 'needs info' items."""
    con = db()
    out = {}
    for r in con.execute("SELECT game_id, type, COUNT(*) n FROM events GROUP BY game_id, type"):
        out.setdefault(r["game_id"], {})[r["type"]] = r["n"]
    for r in con.execute("""SELECT game_id, COUNT(*) n FROM events
                            WHERE type='marker' OR (type='shot' AND
                              (x IS NULL OR (team='us' AND player_id IS NULL)))
                            GROUP BY game_id"""):
        out.setdefault(r["game_id"], {})["todo"] = r["n"]
    con.close()
    return out


@app.get("/api/me")
def me():
    # ponytail: auth is phase 2; everyone is the seeded admin for now
    con = db()
    row = dict(con.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone())
    con.close()
    return row



# ---------------------------------------------------------------- xG / xGOT
# Logistic distance+angle models, least-squares fitted to published NHL
# location values (league SOG sh% ~7.2% 22-23; crease ~15-25%; slot 10-15%;
# perimeter 2-4%; slot = 15-30 ft / 20-40 deg). Sources in MANUAL.md.
# Swap these functions to upgrade the models - the only place xG lives.
NET_X, NET_Y = 189.0, 42.5

# NHL "house" / home plate: posts -> faceoff dots -> across the top of circles
HOUSE = [(189, 39.5), (169, 20.5), (154, 20.5), (154, 64.5), (169, 64.5), (189, 45.5)]


def in_slot(x, y):
    if x is None or y is None:
        return False
    inside = False
    for i in range(len(HOUSE)):
        x1, y1 = HOUSE[i]
        x2, y2 = HOUSE[(i + 1) % len(HOUSE)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _dist_angle(x, y):
    d = math.hypot(NET_X - x, NET_Y - y)
    a = math.atan2(abs(y - NET_Y), max(NET_X - x, 0.1))
    return d, a


def xg_value(x, y):
    """P(goal | shot attempt from x,y). Fit: crease .20, slot .10, circles .04,
    point .018, sharp-angle close .045."""
    if x is None or y is None:
        return None
    d, a = _dist_angle(x, y)
    z = -0.895 - 0.050 * d - 1.355 * a
    return round(1 / (1 + math.exp(-z)), 4)


def xgot_value(x, y, net_x, net_y):
    """P(goal | shot ON GOAL from x,y aimed at net_x,net_y % across the net).
    Base: on-goal logistic (crease .25, slot .13, circles .055, point .025).
    Placement factor from published shot-target effects: corners and upper net
    beat center mass, mild five-hole bump; goalie chest/center is worst."""
    if None in (x, y, net_x, net_y):
        return None
    d, a = _dist_angle(x, y)
    base = 1 / (1 + math.exp(0.633 + 0.048 * d + 1.328 * a))
    h = abs(net_x - 50) / 50          # 0 = center, 1 = post
    v = 1 - net_y / 100               # 0 = along the ice, 1 = crossbar
    m = 0.35 + 1.35 * h ** 1.5 + 0.55 * v
    if h < 0.2 and net_y > 78:        # five-hole
        m += 0.45
    return round(min(1.0, base * min(m, 2.6)), 4)


# ---------------------------------------------------------------- stats engine

def elapsed(period, clock, plen):
    return (period - 1) * plen + (plen - clock)


def analyze_game(game, evs):
    """Per-game derived data: per-shot game state + xG, PP/PK intervals, TOI, on-ice."""
    plen = game["period_len"] or 1200
    for e in evs:
        e["t"] = elapsed(e["period"], e["clock"], plen)
    evs.sort(key=lambda e: (e["t"], e["id"]))
    game_end = max([3 * plen] + [e["t"] for e in evs])

    # penalty intervals; pim>=10 is a misconduct: PIM counts, strength unaffected
    pens = [e for e in evs if e["type"] == "penalty"]
    ivs = [{"s": p["t"], "e": p["t"] + (p["pim"] or 2) * 60, "team": p["team"],
            "minor": (p["pim"] or 2) <= 2}
           for p in pens if (p["pim"] or 2) < 10]
    overrides = sorted([e for e in evs if e["type"] == "override"], key=lambda e: e["t"])

    def state_at(t):
        forced = None
        for o in overrides:
            if o["t"] <= t:
                forced = o["override"]
        if forced and forced != "auto":
            return forced
        au = min(2, sum(1 for iv in ivs if iv["team"] == "us" and iv["s"] <= t < iv["e"]))
        ao = min(2, sum(1 for iv in ivs if iv["team"] == "opp" and iv["s"] <= t < iv["e"]))
        return "pp" if ao > au else "pk" if au > ao else "5v5"
        # coincidental minors give au==ao -> 4v4, reported as 5v5

    # annotate goals in time order; a PP goal ends the earliest-expiring
    # active minor of the shorthanded team (adjusting the interval as we go)
    shots = [e for e in evs if e["type"] == "shot"]
    for e in shots:
        if e["result"] != "goal":
            continue
        e["state"] = state_at(e["t"])
        other = "opp" if e["team"] == "us" else "us"
        scoring_up = (e["team"] == "us" and e["state"] == "pp") or \
                     (e["team"] == "opp" and e["state"] == "pk")
        if scoring_up:
            active = [iv for iv in ivs if iv["team"] == other and iv["minor"]
                      and iv["s"] <= e["t"] < iv["e"]]
            if active:
                min(active, key=lambda iv: iv["e"])["e"] = e["t"]
    for e in shots:
        if "state" not in e:
            e["state"] = state_at(e["t"])
        e["xg"] = xg_value(e["x"], e["y"])
        e["slot"] = in_slot(e["x"], e["y"])
        e["dist_m"] = round(_dist_angle(e["x"], e["y"])[0] * 0.3048, 1) \
            if e["x"] is not None else None
        e["xgot"] = xgot_value(e["x"], e["y"], e["net_x"], e["net_y"]) \
            if e["result"] in ("goal", "on_goal") else None

    # contiguous game-state segments (for TOI split and PP/PK opportunity counts)
    bounds = sorted({0, game_end} | {iv["s"] for iv in ivs} | {iv["e"] for iv in ivs}
                    | {o["t"] for o in overrides})
    bounds = [b for b in bounds if 0 <= b <= game_end]
    segs = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e > s:
            st = state_at(s)
            if segs and segs[-1][2] == st:
                segs[-1] = (segs[-1][0], e, st)
            else:
                segs.append((s, e, st))
    pp_opps = sum(1 for seg in segs if seg[2] == "pp")
    sh_times = sum(1 for seg in segs if seg[2] == "pk")
    # ponytail: a 5v3 counts as one opportunity (one contiguous pp segment)

    # defined line units (2+ members) for together-TOI; "G" is the goalie slot
    line_map = json.loads(game.get("lines") or "{}")
    unit_defs = {}
    for pid, key in line_map.items():
        if key and key != "G":
            unit_defs.setdefault(key, set()).add(int(pid))
    unit_defs = {k: frozenset(v) for k, v in unit_defs.items() if len(v) >= 2}

    # TOI + together-TOI: lineup snapshot i holds until snapshot i+1 (or game end)
    lineups = [e for e in evs if e["type"] == "lineup"]
    toi, onice, pairs, units, shifts = {}, {}, {}, {}, {}
    for i, lu in enumerate(lineups):
        start = lu["t"]
        end = lineups[i + 1]["t"] if i + 1 < len(lineups) else game_end
        ids = json.loads(lu["on_ice"] or "[]")
        for pid in ids:  # per-player shift intervals (merged when back-to-back)
            iv = shifts.setdefault(pid, [])
            if iv and iv[-1][1] == start:
                iv[-1][1] = min(end, game_end)
            else:
                iv.append([start, min(end, game_end)])
        for s, e, st in segs:
            dur = min(e, end) - max(s, start)
            if dur <= 0:
                continue
            for pid in ids:
                d = toi.setdefault(pid, {"total": 0, "5v5": 0, "pp": 0, "pk": 0})
                d["total"] += dur
                d[st] += dur
        full = max(0, min(end, game_end) - start)
        if full:
            sids = sorted(ids)
            for x in range(len(sids)):
                for y in range(x + 1, len(sids)):
                    p = pairs.setdefault((sids[x], sids[y]), {"toi": 0, "gf": 0, "ga": 0})
                    p["toi"] += full
            idset = set(ids)
            for key, mem in unit_defs.items():
                if mem <= idset:
                    u = units.setdefault((key, mem), {"toi": 0, "gf": 0, "ga": 0})
                    u["toi"] += full
    times = [lu["t"] for lu in lineups]
    for sh in shots:
        if sh["result"] not in ("goal", "on_goal"):
            continue
        idx = None
        for i, t in enumerate(times):
            if t <= sh["t"]:
                idx = i
        if idx is None:
            continue
        ids = json.loads(lineups[idx]["on_ice"] or "[]")
        for pid in ids:
            d = onice.setdefault(pid, {"sf": 0, "sa": 0, "gf": 0, "ga": 0})
            d["sf" if sh["team"] == "us" else "sa"] += 1
            if sh["result"] == "goal":
                d["gf" if sh["team"] == "us" else "ga"] += 1
        if sh["result"] == "goal":
            gk = "gf" if sh["team"] == "us" else "ga"
            sids = sorted(ids)
            for x in range(len(sids)):
                for y in range(x + 1, len(sids)):
                    if (sids[x], sids[y]) in pairs:
                        pairs[(sids[x], sids[y])][gk] += 1
            idset = set(ids)
            for key, mem in unit_defs.items():
                if mem <= idset and (key, mem) in units:
                    units[(key, mem)][gk] += 1

    return {"shots": shots, "pens": pens, "pp_opps": pp_opps, "sh_times": sh_times,
            "toi": toi, "onice": onice, "pairs": pairs, "units": units,
            "shifts": shifts, "game_end": game_end, "plen": plen}


@app.get("/api/stats")
def stats(season_id: int = 0, game_ids: str = "", opponent_id: int = 0,
          home: int = -1, state: str = "", period: int = 0):
    con = db()
    where, args = ["1=1"], []
    if season_id:
        where.append("season_id=?"); args.append(season_id)
    if opponent_id:
        where.append("opponent_id=?"); args.append(opponent_id)
    if home in (0, 1):
        where.append("home=?"); args.append(home)
    if game_ids:
        ids = [int(i) for i in game_ids.split(",") if i.strip().isdigit()]
        where.append(f"id IN ({','.join('?' * len(ids))})"); args += ids
    games = [dict(r) for r in con.execute(f"SELECT * FROM games WHERE {' AND '.join(where)}", args)]
    players = {r["id"]: dict(r) for r in con.execute("SELECT * FROM players")}

    team = {"gf": 0, "ga": 0, "sog_f": 0, "sog_a": 0, "att_f": 0, "att_a": 0,
            "xg_f": 0.0, "xg_a": 0.0, "xgot_f": 0.0, "xgot_a": 0.0,
            "slot_f": 0, "slot_a": 0, "pp_opps": 0, "ppg": 0, "sh_times": 0,
            "ppga": 0, "pp_sog": 0, "pens_zone": {"off": 0, "neu": 0, "def": 0},
            "pim": 0, "by_period": {},
            "fo_w": 0, "fo_l": 0, "entries": 0, "entries_ctrl": 0,
            "exits": 0, "exits_ctrl": 0}
    pstats = {}
    all_shots = []
    pairs_all, units_all = {}, {}
    xrows = {}  # per-player faceoff / entry / exit counts
    shifts_out = None

    def xrow(pid):
        return xrows.setdefault(pid, {"fo_t": 0, "fo_w": 0, "en": 0, "en_ctrl": 0,
                                      "ex": 0, "ex_ctrl": 0})

    def prow(pid):
        if pid not in pstats:
            p = players.get(pid, {})
            pstats[pid] = {"player_id": pid, "number": p.get("number"),
                           "name": p.get("name", f"#{pid}"), "position": p.get("position", ""),
                           "gp": 0, "g": 0, "a": 0, "sog": 0, "att": 0, "blk": 0,
                           "pen": 0, "pim": 0, "screens": 0, "xg": 0.0, "xgot": 0.0,
                           "toi": 0, "toi_5v5": 0, "toi_pp": 0, "toi_pk": 0,
                           "sf_on": 0, "sa_on": 0, "gf_on": 0, "ga_on": 0,
                           "sog_5v5": 0}
        return pstats[pid]

    for g in games:
        evs = [dict(r) for r in con.execute("SELECT * FROM events WHERE game_id=?", (g["id"],))]
        a = analyze_game(g, evs)
        for pid in json.loads(g["roster"] or "[]"):
            prow(pid)["gp"] += 1
        team["pp_opps"] += a["pp_opps"]
        team["sh_times"] += a["sh_times"]
        for pid, d in a["toi"].items():
            r = prow(pid)
            r["toi"] += d["total"]; r["toi_5v5"] += d["5v5"]
            r["toi_pp"] += d["pp"]; r["toi_pk"] += d["pk"]
        for pid, d in a["onice"].items():
            r = prow(pid)
            r["sf_on"] += d["sf"]; r["sa_on"] += d["sa"]
            r["gf_on"] += d["gf"]; r["ga_on"] += d["ga"]
        for k, d in a["pairs"].items():
            p = pairs_all.setdefault(k, {"toi": 0, "gf": 0, "ga": 0})
            p["toi"] += d["toi"]; p["gf"] += d["gf"]; p["ga"] += d["ga"]
        for k, d in a["units"].items():
            u = units_all.setdefault(k, {"toi": 0, "gf": 0, "ga": 0})
            u["toi"] += d["toi"]; u["gf"] += d["gf"]; u["ga"] += d["ga"]
        if len(games) == 1:
            shifts_out = {"plen": a["plen"], "end": a["game_end"], "by_player": a["shifts"]}

        for e2 in evs:  # faceoffs / zone entries / exits (quick-logged extras)
            if e2["type"] not in ("faceoff", "entry", "exit"):
                continue
            if period and e2["period"] != period:
                continue
            if e2["type"] == "faceoff":
                team["fo_w" if e2["team"] == "us" else "fo_l"] += 1
                if e2["player_id"]:
                    r = xrow(e2["player_id"])
                    r["fo_t"] += 1
                    if e2["team"] == "us":
                        r["fo_w"] += 1
            else:
                key = "entries" if e2["type"] == "entry" else "exits"
                ctrl = e2["detail"] == "controlled"
                team[key] += 1
                if ctrl:
                    team[key + "_ctrl"] += 1
                if e2["player_id"]:
                    r = xrow(e2["player_id"])
                    pk2 = "en" if e2["type"] == "entry" else "ex"
                    r[pk2] += 1
                    if ctrl:
                        r[pk2 + "_ctrl"] += 1

        for sh in a["shots"]:
            if sh["team"] == "us" and sh["result"] == "goal" and sh["state"] == "pp":
                team["ppg"] += 1
            if sh["team"] == "opp" and sh["result"] == "goal" and sh["state"] == "pk":
                team["ppga"] += 1
            if sh["team"] == "us" and sh["state"] == "pp" and sh["result"] in ("goal", "on_goal"):
                team["pp_sog"] += 1
            if state and sh["state"] != state:
                continue
            if period and sh["period"] != period:
                continue
            all_shots.append({k: sh[k] for k in
                              ("game_id", "team", "player_id", "x", "y", "result",
                               "net_x", "net_y", "state", "period", "xg", "xgot",
                               "slot", "dist_m")})
            for_us = sh["team"] == "us"
            on_goal = sh["result"] in ("goal", "on_goal")
            team["att_f" if for_us else "att_a"] += 1
            if sh["xg"]:
                team["xg_f" if for_us else "xg_a"] += sh["xg"]
            if sh["xgot"]:
                team["xgot_f" if for_us else "xgot_a"] += sh["xgot"]
            if sh["slot"] and on_goal:
                team["slot_f" if for_us else "slot_a"] += 1
            bp = team["by_period"].setdefault(sh["period"], {"sf": 0, "sa": 0})
            if on_goal:
                team["sog_f" if for_us else "sog_a"] += 1
                bp["sf" if for_us else "sa"] += 1
            if sh["result"] == "goal":
                team["gf" if for_us else "ga"] += 1
            if for_us and sh["player_id"]:
                r = prow(sh["player_id"])
                r["att"] += 1
                if sh["xg"]:
                    r["xg"] += sh["xg"]
                if sh["xgot"]:
                    r["xgot"] += sh["xgot"]
                if on_goal:
                    r["sog"] += 1
                    if sh["state"] == "5v5":
                        r["sog_5v5"] += 1
                if sh["result"] == "goal":
                    r["g"] += 1
                    for ak in ("assist1_id", "assist2_id"):
                        if sh[ak]:
                            prow(sh[ak])["a"] += 1
                    if sh["screen_id"]:
                        prow(sh["screen_id"])["screens"] += 1
            if not for_us and sh["result"] == "blocked" and sh["blocker_id"]:
                prow(sh["blocker_id"])["blk"] += 1

        for p in a["pens"]:
            if period and p["period"] != period:
                continue
            if p["team"] == "us":
                team["pim"] += p["pim"] or 2
                if p["zone"]:
                    team["pens_zone"][p["zone"]] += 1
                if p["player_id"]:
                    r = prow(p["player_id"])
                    r["pen"] += 1; r["pim"] += p["pim"] or 2
    con.close()

    team["sh_pct"] = round(100 * team["gf"] / team["sog_f"], 1) if team["sog_f"] else 0
    team["pp_pct"] = round(100 * team["ppg"] / team["pp_opps"], 1) if team["pp_opps"] else 0
    team["pk_pct"] = round(100 * (team["sh_times"] - team["ppga"]) / team["sh_times"], 1) \
        if team["sh_times"] else 0
    team["shots_per_pp"] = round(team["pp_sog"] / team["pp_opps"], 2) if team["pp_opps"] else 0
    team["xg_f"] = round(team["xg_f"], 2)
    team["xg_a"] = round(team["xg_a"], 2)
    team["xgot_f"] = round(team["xgot_f"], 2)
    team["xgot_a"] = round(team["xgot_a"], 2)
    fo_total = team["fo_w"] + team["fo_l"]
    team["fo_pct"] = round(100 * team["fo_w"] / fo_total, 1) if fo_total else 0

    out = []
    for r in pstats.values():
        r["p"] = r["g"] + r["a"]
        r["sh_pct"] = round(100 * r["g"] / r["sog"], 1) if r["sog"] else 0
        r["xg"] = round(r["xg"], 2)
        r["xgot"] = round(r["xgot"], 2)
        r["p60"] = round(r["p"] * 3600 / r["toi"], 2) if r["toi"] else 0
        r["s60_5v5"] = round(r["sog_5v5"] * 3600 / r["toi_5v5"], 2) if r["toi_5v5"] else 0
        out.append(r)
    out.sort(key=lambda r: (-r["p"], -r["g"], r["name"]))

    def tag(pid):
        p = players.get(pid)
        return f"#{p['number']} {p['name']}" if p else str(pid)

    is_g = lambda pid: (players.get(pid) or {}).get("position", "").upper() == "G"
    pairs_out = sorted(
        [{"ids": [a, b], "players": f"{tag(a)} + {tag(b)}",
          "toi": v["toi"], "gf": v["gf"], "ga": v["ga"]}
         for (a, b), v in pairs_all.items() if not (is_g(a) or is_g(b))],
        key=lambda r: -r["toi"])
    units_out = sorted(
        [{"line": key, "players": ", ".join(tag(p) for p in sorted(mem)),
          "toi": v["toi"], "gf": v["gf"], "ga": v["ga"]}
         for (key, mem), v in units_all.items()],
        key=lambda r: (r["line"], -r["toi"]))

    extras_out = sorted(
        [dict(r, player_id=pid, number=(players.get(pid) or {}).get("number"),
              name=(players.get(pid) or {}).get("name", str(pid)),
              fo_pct=round(100 * r["fo_w"] / r["fo_t"], 1) if r["fo_t"] else 0)
         for pid, r in xrows.items()],
        key=lambda r: -(r["fo_t"] + r["en"] + r["ex"]))

    return {"games": [{"id": g["id"], "opponent_id": g["opponent_id"], "date": g["date"],
                       "home": g["home"], "score_us": g["score_us"],
                       "score_opp": g["score_opp"]} for g in games],
            "team": team, "players": out, "shots": all_shots,
            "together": {"pairs": pairs_out, "units": units_out},
            "extras": extras_out, "shifts": shifts_out}


# ---------------------------------------------------------------- generic CRUD

@app.get("/api/{table}")
def list_rows(table: str, request: Request):
    cols = COLS.get(table)
    if cols is None:
        raise HTTPException(404)
    where, args = "", []
    filters = [(k, v) for k, v in request.query_params.items() if k in cols or k == "id"]
    if filters:
        where = " WHERE " + " AND ".join(f"{k}=?" for k, _ in filters)
        args = [v for _, v in filters]
    con = db()
    rows = [dict(r) for r in con.execute(f"SELECT * FROM {table}{where} ORDER BY id", args)]
    con.close()
    return rows


@app.post("/api/{table}")
async def create_row(table: str, request: Request):
    cols = COLS.get(table)
    if cols is None:
        raise HTTPException(404)
    body = await request.json()
    data = {k: body[k] for k in cols if k in body}
    if not data:
        raise HTTPException(400, "no valid columns")
    con = db()
    try:
        cur = con.execute(
            f"INSERT INTO {table}({','.join(data)}) VALUES ({','.join('?' * len(data))})",
            list(data.values()))
        con.commit()
        row = dict(con.execute(f"SELECT * FROM {table} WHERE id=?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, str(e))
    finally:
        con.close()
    return row


@app.put("/api/{table}/{row_id}")
async def update_row(table: str, row_id: int, request: Request):
    cols = COLS.get(table)
    if cols is None:
        raise HTTPException(404)
    body = await request.json()
    data = {k: body[k] for k in cols if k in body}
    if not data:
        raise HTTPException(400, "no valid columns")
    con = db()
    try:
        con.execute(f"UPDATE {table} SET {','.join(k + '=?' for k in data)} WHERE id=?",
                    list(data.values()) + [row_id])
        con.commit()
        row = con.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, str(e))
    finally:
        con.close()
    if not row:
        raise HTTPException(404)
    return dict(row)


@app.delete("/api/{table}/{row_id}")
def delete_row(table: str, row_id: int):
    if table not in COLS:
        raise HTTPException(404)
    con = db()
    con.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
    con.commit()
    con.close()
    return {"ok": True}



# ---------------------------------------------------------------- static

@app.get("/manual")
def manual():
    return FileResponse(os.path.join(HERE, "MANUAL.md"), media_type="text/markdown; charset=utf-8")


app.mount("/", StaticFiles(directory=os.path.join(HERE, "static"), html=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
