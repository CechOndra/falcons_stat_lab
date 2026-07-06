# Falcons Stat Lab

Local-first logging & analytics for VŠE Falcons Prague game videos:
watch the game file in the browser, log events with keyboard shortcuts,
get team/player stats, shot heat maps, TOI, PP/PK and xG.

## Run

```
pip install -r requirements.txt
python app.py
```

→ http://localhost:8000 — data lives in `falcons.db` (SQLite, copy = backup).
Videos are opened straight from disk, never uploaded.

## Docs

Full manual (setup, clock calibration, shortcut cheat sheet, logging
workflow, dashboard): [MANUAL.md](MANUAL.md) or `/manual` in the app.

## Test

```
python test_app.py
```

## Layout

- `app.py` — FastAPI + SQLite backend, stats engine, xG model (single file)
- `static/index.html` — the whole frontend (no build step)
- `seed/` — editable teams + roster CSV templates
