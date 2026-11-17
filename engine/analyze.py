"""Analyse d'une séance réalisée : prévu vs fait, à partir des tours (laps) Garmin."""
from .paces import fmt_pace, fmt_time, vdot_from_race

TOL = 4  # s/km de tolérance autour de la cible

VERDICTS = {
    "reussie": "Séance réussie",
    "correcte": "Séance correcte",
    "a_revoir": "À revoir",
    "incomplete": "Incomplète",
}


def flatten(steps):
    out = []
    for s in steps:
        if s["k"] == "repeat":
            for _ in range(s["fois"]):
                out.extend(flatten(s["etapes"]))
        else:
            out.append(s)
    return out


def lap_pace(lap):
    d = lap.get("distance") or 0
    t = lap.get("duration") or lap.get("movingDuration") or 0
    return t / (d / 1000) if d > 30 and t else None


def summary(act):
    d = (act.get("distance") or 0) / 1000
    t = act.get("duration") or 0
    return {
        "distance_km": round(d, 2),
        "duree": fmt_time(t),
        "duree_s": round(t),
        "allure": fmt_pace(t / d) if d else None,
        "fc": round(act["averageHR"]) if act.get("averageHR") else None,
        "heure": (act.get("startTimeLocal") or "")[11:16] or None,
    }


def _work_laps(session, laps):
    """Retourne [(lap, étape prévue)] pour les efforts de la séance."""
    plan = flatten(session["etapes"])
    efforts = [s for s in plan if s["k"] == "effort" and s.get("zone") != "libre"]
    if not efforts:
        return [], efforts
    if len(laps) == len(plan):
        return [(l, s) for l, s in zip(laps, plan) if s["k"] == "effort" and s.get("zone") != "libre"], efforts
    tagged = [l for l in laps if (l.get("intensityType") or "").upper() == "INTERVAL"]
    if tagged:
        return list(zip(tagged, efforts)), efforts
    # Heuristique : tours rapides dont la distance/durée ressemble à l'effort prévu
    ref = efforts[0]
    fast_limit = ref["allure"][0] + 25 if ref.get("allure") else 330
    cand = []
    for l in laps:
        p = lap_pace(l)
        if not p or p > fast_limit:
            continue
        if "distance_m" in ref and abs(l["distance"] - ref["distance_m"]) > 0.25 * ref["distance_m"]:
            continue
        if "duree_s" in ref and abs(l["duration"] - ref["duree_s"]) > 0.25 * ref["duree_s"]:
            continue
        cand.append(l)
    return list(zip(cand, efforts)), efforts


def _quality(session, act, laps):
    pairs, efforts = _work_laps(session, laps)
    tours, statuts = [], []
    for i, (lap, st) in enumerate(pairs):
        p = lap_pace(lap)
        slow, fast = st["allure"]
        stt = "lent" if p > slow + TOL else "vite" if p < fast - TOL else "ok"
        statuts.append(stt)
        tours.append({"n": i + 1, "allure_s": round(p), "allure": fmt_pace(p), "cible": [slow, fast], "statut": stt,
                      "fc": round(lap["averageHR"]) if lap.get("averageHR") else None})
    n_plan, n_done = len(efforts), len(tours)
    points = []
    if n_done == 0:
        return {"verdict": "incomplete", "resume": "Je ne retrouve pas les fractions dans tes tours.",
                "points": ["Lance la séance depuis la montre (Entraînement > Séances) pour que chaque fraction soit un tour."],
                "tours": []}
    ok, lent, vite = statuts.count("ok"), statuts.count("lent"), statuts.count("vite")
    fade = tours[-1]["allure_s"] - tours[0]["allure_s"]
    cible = efforts[0]["allure"]
    moy = sum(t["allure_s"] for t in tours) / n_done
    points.append(f"Moyenne {fmt_pace(moy)}/km pour une cible {fmt_pace(cible[1])}–{fmt_pace(cible[0])}.")
    if n_done < 0.75 * n_plan:
        verdict, resume = "incomplete", f"{n_done} fractions sur {n_plan}."
        points.append("Si c'était trop dur, c'est une info utile : la prochaine reste au même niveau.")
    elif lent >= n_done / 2:
        verdict, resume = "a_revoir", f"{lent} fractions sur {n_done} plus lentes que la cible."
        points.append("Fatigue, chaleur ou cible trop ambitieuse : on ne monte pas d'un cran la prochaine fois.")
    elif ok >= 0.7 * n_done and fade <= 8:
        verdict, resume = "reussie", f"{ok}/{n_done} fractions dans l'allure, régulier jusqu'au bout."
    elif vite >= n_done / 2:
        verdict, resume = "correcte", f"{vite} fractions sur {n_done} trop rapides."
        points.append("Plus vite que prévu ne rapporte rien de plus : vise la précision. Si c'est facile, le prochain test remontera tes allures.")
    else:
        verdict, resume = "correcte", f"{ok}/{n_done} fractions dans l'allure."
    if fade > 8:
        points.append(f"La dernière fraction est {fade} s/km plus lente que la première : pars un peu plus prudemment.")
    elif n_done >= 3 and verdict != "incomplete":
        points.append("Allure stable du début à la fin.")
    return {"verdict": verdict, "resume": resume, "points": points, "tours": tours}


def _drift(laps):
    hr = [(l.get("averageHR"), lap_pace(l)) for l in laps if l.get("averageHR") and lap_pace(l)]
    if len(hr) < 4:
        return None
    h = len(hr) // 2
    a = sum(x for x, _ in hr[:h]) / h
    b = sum(x for x, _ in hr[h:]) / (len(hr) - h)
    pa = sum(p for _, p in hr[:h]) / h
    pb = sum(p for _, p in hr[h:]) / (len(hr) - h)
    return round(b - a) if pb <= pa + 5 else None


def _easy(session, act, laps):
    step = session["etapes"][0]
    planned = session["duree_estimee_s"]
    dur = act.get("duration") or 0
    dist = (act.get("distance") or 0) / 1000
    pace = dur / dist if dist else 0
    hr = act.get("averageHR")
    points, extra = [], {}
    ratio = dur / planned if planned else 1
    if ratio < 0.6:
        verdict, resume = "incomplete", f"{fmt_time(dur)} sur {fmt_time(planned)} prévues."
    elif step.get("fc") and hr:
        lo, hi = step["fc"]
        extra = {"fc_cible": [lo, hi], "fc_moy": round(hr)}
        if hr > hi + 3:
            verdict, resume = "correcte", f"Cardio trop haut : {round(hr)} bpm pour une cible {lo}–{hi}."
        else:
            verdict, resume = "reussie", f"{round(hr)} bpm, pile en endurance."
    elif step.get("allure"):
        ef = step["allure"]
        extra = {"allure_cible": ef}
        if pace < ef[1] - 8:
            verdict, resume = "correcte", f"Trop rapide : {fmt_pace(pace)}/km pour une cible {fmt_pace(ef[1])}–{fmt_pace(ef[0])}."
        else:
            verdict, resume = "reussie", f"{fmt_pace(pace)}/km, en endurance."
    else:
        verdict, resume = "reussie", f"{fmt_pace(pace)}/km." if pace else "Sortie faite."
    d = _drift(laps)
    if d and d >= 7:
        points.append(f"Ton cœur monte de {d} bpm en deuxième partie à allure égale.")
    return {"verdict": verdict, "resume": resume, "points": points, "tours": [], **extra}


def _timed(session, act, laps):
    target = next(s for s in flatten(session["etapes"]) if s["k"] == "effort")["distance_m"]
    best = None
    pairs, _ = _work_laps(session, laps)
    if pairs:
        best = pairs[0][0]
    else:
        near = [l for l in laps if abs((l.get("distance") or 0) - target) <= 0.03 * target]
        best = max(near, key=lambda l: l["distance"]) if near else None
    if not best and abs((act.get("distance") or 0) - target) <= 0.12 * target:
        best = act
    if not best:
        return {"verdict": "incomplete", "resume": f"Je ne retrouve pas de bloc de {target / 1000:g} km.",
                "points": ["Après l'échauffement, appuie sur Tour pour lancer le chrono."], "tours": []}
    t = best["duration"] * target / best["distance"]
    v = vdot_from_race(target, t)
    return {"verdict": "reussie", "resume": f"{target / 1000:g} km en {fmt_time(t)} ({fmt_pace(t / target * 1000)}/km).",
            "points": ["Tes allures sont recalculées à partir de ce chrono."], "tours": [],
            "chrono_s": round(t), "vdot": round(v, 2)}


def analyze(session, act, laps):
    st = session["sous_type"]
    if st in ("test", "course"):
        a = _timed(session, act, laps)
    elif st == "ef":
        a = _easy(session, act, laps)
    else:
        a = _quality(session, act, laps)
    a["titre"] = VERDICTS[a["verdict"]]
    a["realise"] = summary(act)
    return a
