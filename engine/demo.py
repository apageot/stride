"""Données simulées pour voir l'app sans Garmin : python -m engine.demo"""
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from .analyze import flatten
from .core import build

ROOT = Path(__file__).resolve().parent.parent
random.seed(7)

# Scénario : petits écarts pour montrer les différents bilans
SCENARIO = {
    "w2-petite": "skip",
    "w2-longue": "drift",
    "w3-allure": "slow",
    "w1-petite": "fast",
}
PLAN_JOUR = {1: "petite", 3: "allure", 5: "bonus", 6: "longue"}  # jours où le coureur simulé sort


def laps_for(session, mode, ef):
    laps, hr = [], 136 if mode != "fast" else 150
    for s in flatten(session["etapes"]):
        if s["k"] in ("continu",):
            km = s["duree_s"] / ((ef[0] + ef[1]) / 2)
            pace = (ef[0] + ef[1]) / 2 + (-25 if mode == "fast" else 0)
            for i in range(int(km)):
                h = hr + (i * (2.2 if mode == "drift" else 0.4))
                laps.append({"distance": 1000, "duration": pace + random.uniform(-6, 6), "averageHR": h})
            continue
        if s.get("zone") == "test":
            laps.append({"distance": s["distance_m"], "duration": 5 * 263 + random.uniform(-5, 5), "averageHR": 178})
            continue
        if s["k"] == "effort" and s.get("allure"):
            slow, fast = s["allure"]
            p = (slow + fast) / 2 + random.uniform(-3, 3) + (9 if mode == "slow" else 0)
            if "distance_m" in s:
                laps.append({"distance": s["distance_m"], "duration": p * s["distance_m"] / 1000, "averageHR": 172})
            else:
                laps.append({"distance": s["duree_s"] / p * 1000, "duration": s["duree_s"], "averageHR": 168})
            continue
        dur = s.get("duree_s", 60)
        p = ef[0] + (70 if s["k"] == "recup" else 0) if not (s["k"] == "effort") else 290
        laps.append({"distance": dur / p * 1000, "duration": dur, "averageHR": 150 if s["k"] != "recup" else 140})
    return laps


def fake_series(laps):
    """Parcours en boucle + vitesse/altitude/cardio réalistes, pour la démo."""
    n = 140
    total = sum(l["duration"] for l in laps)
    speed, hr, t = [], [], 0
    for i in range(n):
        tt = total * i / n
        acc = 0
        for l in laps:
            if acc + l["duration"] >= tt:
                break
            acc += l["duration"]
        speed.append(round(l["distance"] / l["duration"] * random.uniform(.96, 1.04), 2))
        hr.append(round(l["averageHR"] + random.uniform(-3, 3)))
    # boucle le long des quais de la Garonne (Prairie des Filtres → Pont des Catalans → Saint-Michel)
    way = [(43.5958, 1.4352), (43.5995, 1.4338), (43.6040, 1.4318), (43.6068, 1.4304), (43.6074, 1.4330),
           (43.6046, 1.4366), (43.6012, 1.4392), (43.5975, 1.4405), (43.5932, 1.4408), (43.5905, 1.4392),
           (43.5912, 1.4365), (43.5935, 1.4356), (43.5958, 1.4352)]
    pts = []
    for (a1, o1), (a2, o2) in zip(way, way[1:]):
        for j in range(13):
            t = j / 13
            pts.append([round(a1 + (a2 - a1) * t + random.uniform(-.00004, .00004), 5),
                        round(o1 + (o2 - o1) * t + random.uniform(-.00004, .00004), 5)])
    alt = [round(52 + 9 * math.sin(i / 17) + 4 * math.sin(i / 5) + random.uniform(-.6, .6), 1) for i in range(n)]
    return {"trace": pts, "vitesse": speed, "altitude": alt, "fc": hr}


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    today = date(2026, 11, 14)
    cfg["debut"] = "2026-10-19"
    state, acts, laps_by_id, series = {}, [], {}, {}
    d = date.fromisoformat(cfg["debut"])
    aid = 1000
    while d < today:
        data, state = build(cfg, state, acts, laps_by_id, d, series)
        slot = PLAN_JOUR.get(d.weekday())
        week = next(w for w in data["semaines"] if w["debut"] <= d.isoformat() <= w["fin"])
        s = next((x for x in week["seances"] if x["type"] == slot and x["statut"] in ("a_faire", "facultative")), None)
        mode = SCENARIO.get(f"w{week['num']}-{slot}")
        if s and mode != "skip" and not (slot == "bonus" and week["num"] != 2):
            ef = data["allures"]["ef"]["s"]
            laps = laps_for(s, mode, ef)
            aid += 1
            dist = sum(l["distance"] for l in laps)
            dur = sum(l["duration"] for l in laps)
            acts.append({"activityId": aid, "activityName": "Course à pied", "startTimeLocal": f"{d} 18:30:00",
                         "distance": dist, "duration": dur, "averageSpeed": dist / dur,
                         "averageHR": sum(l["averageHR"] * l["duration"] for l in laps) / dur,
                         "maxHR": max(l["averageHR"] for l in laps) + (12 if s["type"] == "allure" else 6),
                         "activityType": {"typeKey": "running"}})
            laps_by_id[str(aid)] = laps
            series[str(aid)] = fake_series(laps)
        d += timedelta(days=1)
    data, state = build(cfg, state, acts, laps_by_id, today, series)
    faites = [s for w in data["semaines"] for s in w["seances"] if s.get("statut") == "faite"]
    allures = [s for s in faites if s["type"] == "allure" and s["analyse"]["verdict"] in ("reussie", "correcte")]
    autres = [s for s in faites if s["type"] != "allure"]
    for s, v in list(zip(allures, ["facile", "dur"])) + list(zip(autres, ["ok", "facile", "ok", "dur"])):
        state.setdefault("ressentis", {})[s["id"]] = v
    data, state = build(cfg, state, acts, laps_by_id, today, series)
    data["demo"] = True
    out = ROOT / "docs" / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
