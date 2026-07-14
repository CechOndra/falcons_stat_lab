"""End-to-end check of the API + stats engine. Run: python test_app.py"""
import os
import tempfile

os.environ["FALCONS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

import app as appmod  # noqa: E402

client = TestClient(appmod.app)


def post(path, json=None, **kw):
    r = client.post(path, json=json, **kw)
    assert r.status_code == 200, f"{path}: {r.text}"
    return r.json()


def ev(game_id, type_, team, clock, **kw):
    return post("/api/events", dict(game_id=game_id, type=type_, team=team,
                                    period=1, clock=clock, video_ts=clock / 10, **kw))


def main():
    # --- setup: season, opponent, roster ---
    season = post("/api/seasons", {"name": "2024/25 test"})
    opp = post("/api/teams", {"name": "Test Opponent"})
    A = post("/api/players", {"number": 17, "name": "A Shooter", "position": "F"})
    B = post("/api/players", {"number": 9, "name": "B Passer", "position": "F"})
    C = post("/api/players", {"number": 4, "name": "C Blocker", "position": "D"})
    D = post("/api/players", {"number": 33, "name": "D Goalie", "position": "G"})
    a, b, c = A["id"], B["id"], C["id"]

    # CSV roster import
    n0 = len(client.get("/api/players").json())
    r = client.post("/api/roster_csv", content="number,name,position\n55,CSV Guy,F\n66,CSV Two,D\n")
    assert r.json()["imported"] == 2
    assert len(client.get("/api/players").json()) == n0 + 2

    # --- game 1 with a scripted timeline (period_len 1200, clock = s remaining) ---
    g1 = post("/api/games", {"season_id": season["id"], "opponent_id": opp["id"],
                             "date": "2025-02-01", "home": 1, "period_len": 1200,
                             "roster": f'[{a},{b},{c},{D["id"]}]',
                             "lines": f'{{"{a}":"F1","{b}":"F1","{c}":"D1","{D["id"]}":"G"}}'})["id"]
    ev(g1, "lineup", "us", 1200, on_ice=f"[{a},{b}]")                       # t=0: A,B on
    ev(g1, "shot", "us", 1140, player_id=a, x=170, y=40, result="on_goal")  # t=60, 5v5
    ev(g1, "penalty", "opp", 1100, pim=2)                                   # t=100 -> our PP
    ev(g1, "shot", "us", 1050, player_id=a, x=175, y=42, result="goal",
       assist1_id=b, net_x=90, net_y=20)                                    # t=150 PP goal, ends penalty
    ev(g1, "lineup", "us", 1000, on_ice=f"[{a}]")                           # t=200: only A
    ev(g1, "penalty", "us", 900, player_id=c, pim=2, zone="def")            # t=300 -> our PK
    ev(g1, "shot", "opp", 850, x=170, y=40, result="on_goal")               # t=350, PK survived
    ev(g1, "shot", "opp", 700, x=160, y=40, result="blocked", blocker_id=c) # t=500, 5v5 again
    e_miss = ev(g1, "shot", "us", 600, player_id=b, x=120, y=10, result="missed")  # t=600
    ev(g1, "override", "us", 500, override="pk")                            # t=700 forced PK
    ev(g1, "shot", "us", 450, player_id=a, x=150, y=30, result="on_goal")   # t=750 counts as PK
    ev(g1, "override", "us", 400, override="auto")                          # t=800 back to auto

    s = client.get(f"/api/stats?game_ids={g1}").json()
    t = s["team"]
    assert (t["gf"], t["ga"]) == (1, 0)
    assert (t["sog_f"], t["sog_a"], t["att_f"], t["att_a"]) == (3, 1, 4, 2)
    assert t["sh_pct"] == 33.3
    assert (t["pp_opps"], t["ppg"], t["pp_pct"], t["shots_per_pp"]) == (1, 1, 100.0, 1.0)
    assert (t["sh_times"], t["ppga"], t["pk_pct"]) == (2, 0, 100.0), t  # derived PK + forced override PK
    assert t["pim"] == 2 and t["pens_zone"] == {"off": 0, "neu": 0, "def": 1}
    assert t["by_period"]["1"] == {"sf": 3, "sa": 1}
    assert 0 < t["xg_f"] < 2 and 0 < t["xg_a"] < 1
    assert (t["slot_f"], t["slot_a"]) == (2, 1)  # house SOG for/against
    assert t["xgot_f"] > 0 and t["xgot_a"] == 0  # only the placed PP goal has xGOT
    assert len(s["shots"]) == 6 and all(0 < sh["xg"] < 1 for sh in s["shots"])
    # distances reported in meters: shot from (170,40) is ~5.8 m out
    assert any(abs(sh["dist_m"] - 5.8) < 0.2 for sh in s["shots"])

    P = {p["player_id"]: p for p in s["players"]}
    pa, pb, pc = P[a], P[b], P[c]
    assert (pa["g"], pa["a"], pa["p"], pa["sog"], pa["att"]) == (1, 0, 1, 3, 3)
    assert pa["xgot"] > 0
    assert (pa["toi"], pa["toi_pp"], pa["toi_pk"], pa["toi_5v5"]) == (3600, 50, 220, 3330)
    assert (pa["p60"], pa["s60_5v5"]) == (1.0, 1.08)
    assert (pa["sf_on"], pa["sa_on"], pa["gf_on"], pa["ga_on"]) == (3, 1, 1, 0)
    assert (pb["a"], pb["p"], pb["att"], pb["sog"]) == (1, 1, 1, 0)
    assert (pb["toi"], pb["toi_pp"], pb["toi_5v5"], pb["p60"]) == (200, 50, 150, 18.0)
    assert (pb["sf_on"], pb["gf_on"]) == (2, 1)
    assert (pc["blk"], pc["pen"], pc["pim"]) == (1, 1, 2)
    assert all(P[k]["gp"] == 1 for k in (a, b, c))

    # together on ice: A+B share 0..200 (pair + defined F1 unit), goal at t=150 counts
    tg = s["together"]
    ab = [p for p in tg["pairs"] if "A Shooter" in p["players"] and "B Passer" in p["players"]]
    assert ab and (ab[0]["toi"], ab[0]["gf"], ab[0]["ga"]) == (200, 1, 0), tg["pairs"]
    f1 = [u for u in tg["units"] if u["line"] == "F1"]
    assert f1 and (f1[0]["toi"], f1[0]["gf"]) == (200, 1), tg["units"]
    assert not any(u["line"] == "D1" for u in tg["units"])  # 1-man "unit" is not a unit

    # state / period filters
    pp = client.get(f"/api/stats?game_ids={g1}&state=pp").json()
    assert pp["team"]["sog_f"] == 1 and pp["team"]["gf"] == 1 and len(pp["shots"]) == 1
    p1 = client.get(f"/api/stats?game_ids={g1}&period=1").json()
    assert p1["team"]["sog_f"] == 3

    # edit + delete an event, stats follow
    r = client.put(f"/api/events/{e_miss['id']}", json={"result": "on_goal"})
    assert r.status_code == 200
    assert client.get(f"/api/stats?game_ids={g1}").json()["team"]["sog_f"] == 4
    assert client.delete(f"/api/events/{e_miss['id']}").status_code == 200
    t2 = client.get(f"/api/stats?game_ids={g1}").json()["team"]
    assert (t2["sog_f"], t2["att_f"]) == (3, 3)

    # session persistence round-trip
    r = client.put(f"/api/games/{g1}", json={"calibration": '{"period":2,"clock":900}',
                                             "last_video_pos": 1234.5, "last_video_idx": 1,
                                             "video_files": '[{"name":"p1.mp4","period":1}]'})
    g = client.get(f"/api/games?id={g1}").json()[0]
    assert g["last_video_pos"] == 1234.5 and '"p1.mp4"' in g["video_files"]

    # marker events: instant stamp, ignored by stats, convertible via PUT
    mk = ev(g1, "marker", "us", 300, note="faceoff?")
    s3 = client.get(f"/api/stats?game_ids={g1}").json()
    assert s3["team"]["sog_f"] == 3 and s3["team"]["pp_opps"] == 1
    r = client.put(f"/api/events/{mk['id']}", json={"type": "penalty", "team": "opp", "pim": 2})
    assert r.status_code == 200 and r.json()["type"] == "penalty" and r.json()["note"] == "faceoff?"
    assert client.get(f"/api/stats?game_ids={g1}").json()["team"]["pp_opps"] == 2
    assert client.delete(f"/api/events/{mk['id']}").status_code == 200

    # faceoffs + zone entries/exits (quick extras) + shift chart + game flags
    ev(g1, "faceoff", "us", 1195, player_id=a)          # won, taken by A
    ev(g1, "faceoff", "opp", 1000)                      # lost
    ev(g1, "entry", "us", 950, player_id=a, detail="controlled")
    ev(g1, "entry", "us", 940, player_id=b, detail="uncontrolled")
    ev(g1, "exit", "us", 930, player_id=c, detail="controlled")
    sx = client.get(f"/api/stats?game_ids={g1}").json()
    tx = sx["team"]
    assert (tx["fo_w"], tx["fo_l"], tx["fo_pct"]) == (1, 1, 50.0)
    assert (tx["entries"], tx["entries_ctrl"], tx["exits"], tx["exits_ctrl"]) == (2, 1, 1, 1)
    XA = {r["player_id"]: r for r in sx["extras"]}
    assert (XA[a]["fo_t"], XA[a]["fo_w"], XA[a]["fo_pct"], XA[a]["en"]) == (1, 1, 100.0, 1)
    assert XA[c]["ex_ctrl"] == 1
    # single-game filter -> per-player shift intervals; A's two snapshots merge to one shift
    assert sx["shifts"] and sx["shifts"]["by_player"][str(a)] == [[0, 3600]]
    assert sx["shifts"]["by_player"][str(b)] == [[0, 200]]
    assert all("ids" in p for p in sx["together"]["pairs"])
    flags = client.get("/api/game_flags").json()[str(g1)]
    assert flags["shot"] == 5 and flags["lineup"] == 2 and flags["faceoff"] == 2
    assert flags["entry"] == 2 and flags["exit"] == 1 and "todo" not in flags

    # --- game 2: opponent PP goal ends OUR minor ---
    g2 = post("/api/games", {"opponent_id": opp["id"], "period_len": 1200})["id"]
    ev(g2, "penalty", "us", 1100, player_id=c, pim=2)                    # t=100
    ev(g2, "shot", "opp", 1050, x=175, y=42, result="goal")              # t=150 PP goal against
    ev(g2, "shot", "opp", 1000, x=170, y=40, result="on_goal")           # t=200 -> back to 5v5
    s2 = client.get(f"/api/stats?game_ids={g2}").json()
    assert (s2["team"]["sh_times"], s2["team"]["ppga"], s2["team"]["pk_pct"]) == (1, 1, 0.0)
    states = {(sh["result"], sh["state"]) for sh in s2["shots"]}
    assert ("goal", "pk") in states and ("on_goal", "5v5") in states
    assert client.get("/api/stats").json()["shifts"] is None  # multi-game: no shift chart

    # xG calibrated to published NHL anchors: crease ~.20, slot ~.10, point ~.02
    assert 0.17 < appmod.xg_value(181, 42.5) < 0.24
    assert 0.07 < appmod.xg_value(170, 45) < 0.13
    assert appmod.xg_value(134, 42.5) < 0.03
    assert appmod.xg_value(175, 42.5) > appmod.xg_value(175, 20)
    # xGOT: corners beat the goalie's chest; requires placement
    assert appmod.xgot_value(175, 42.5, 95, 15) > 2 * appmod.xgot_value(175, 42.5, 50, 45)
    assert appmod.xgot_value(175, 42.5, None, None) is None
    # slot = NHL home plate
    assert appmod.in_slot(180, 42.5) and appmod.in_slot(160, 30)
    assert not appmod.in_slot(130, 42.5) and not appmod.in_slot(180, 10)

    # static + manual served
    assert client.get("/").status_code == 200 and b"Falcons Stat Lab" in client.get("/").content
    assert client.get("/manual").status_code == 200
    assert client.get("/api/me").json()["role"] == "admin"

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
