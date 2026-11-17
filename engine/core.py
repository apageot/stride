"""Cœur de l'app : rejoue tout le plan depuis le début, associe les sorties Garmin aux séances,
analyse, adapte, et prépare les données de l'interface.

Pas de jours fixes : chaque semaine a 3 séances (footing, séance clé, sortie longue) + un footing bonus
facultatif. Tu les fais quand tu veux ; chaque sortie Garmin est associée à la séance qui lui ressemble.

Tout est recalculé à chaque synchro (déterministe). Les semaines terminées sont figées dans state.json
pour que l'historique ne bouge pas si tu changes la config.
"""
import copy
from datetime import date, datetime, timedelta

from . import plan as P
from .analyze import analyze, summary
from .paces import best_vdot, fmt_pace, fmt_time, parse_time, predict_time, vdot_from_pace, zones

RUN_TYPES = ("running", "treadmill_running", "trail_running", "track_running", "street_running", "indoor_running")
NOMS = {"vma": "Séance VMA", "seuil": "Séance seuil", "specifique": "Séance allure 10 km", "petite": "Footing",
        "longue": "Sortie longue", "bonus": "Footing bonus"}
PCT = {"vma": 0.975, "seuil": 0.875}  # % de VO2max visé par ces fractions


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def act_date(a) -> date:
    return date.fromisoformat((a.get("startTimeLocal") or a.get("startTimeGMT"))[:10])


def is_run(a) -> bool:
    return ((a.get("activityType") or {}).get("typeKey") or "") in RUN_TYPES


def guess_type(a, laps, sessions):
    """Devine à quelle séance correspond une sortie."""
    dur = a.get("duration") or 0
    longue = next((s for s in sessions if s["type"] == "longue"), None)
    paces = [l["duration"] / (l["distance"] / 1000) for l in laps if (l.get("distance") or 0) > 150 and l.get("duration")]
    if paces and len(paces) >= 3 and min(paces) < (sum(paces) / len(paces)) - 25:
        return "allure"
    if longue and dur >= 0.8 * longue["duree_estimee_s"]:
        return "longue"
    return "petite"


def fc_max_of(cfg, runs):
    if cfg.get("fc_max"):
        return int(cfg["fc_max"])
    seen = [a.get("maxHR") for a in runs if a.get("maxHR")]
    return int(max(seen)) if seen and max(seen) >= 150 else None


def spec_pace(vdot, obj_pace, niveau):
    """Allure des séances 'allure 10 km' : part de ton allure 10 km actuelle et rejoint l'objectif."""
    cur = predict_time(vdot, 10000) / 10
    if cur <= obj_pace:
        return obj_pace
    frac = min(1.0, 0.35 + 0.13 * niveau)
    return cur - frac * (cur - obj_pace)


def build(cfg: dict, state: dict, activities: list, laps_by_id: dict, today: date, series_by_id: dict | None = None):
    debut = monday(date.fromisoformat(cfg["debut"]))
    obj = cfg["objectif"]
    obj_s = parse_time(obj["temps"])
    obj_pace = obj_s / obj["distance_km"]
    vdot0 = best_vdot(cfg["records"])
    frozen = state.get("semaines", {})
    ressentis = state.get("ressentis", {})  # {id_séance: "facile" | "ok" | "dur"}
    runs = sorted([a for a in activities if is_run(a) and act_date(a) >= debut], key=lambda a: a.get("startTimeLocal", ""))
    fcmax = fc_max_of(cfg, runs)
    fc_ef = [round(0.65 * fcmax), round(0.77 * fcmax)] if fcmax else None

    ctx = {"vdot": vdot0, "niveaux": {k: 0 for k in ("vma", "seuil", "specifique", "petite", "longue")},
           "allegee_next": False, "bad": 0}
    journal, historique = [], [{"date": debut.isoformat(), "prediction_s": round(predict_time(vdot0, 10000))}]
    weeks, current = [], monday(today)

    def log(d, texte, kind):
        journal.append({"date": d, "texte": texte, "type": kind})

    def set_vdot(new, d):
        before = predict_time(ctx["vdot"], 10000)
        ctx["vdot"] = new
        after = predict_time(new, 10000)
        historique.append({"date": d, "prediction_s": round(after)})
        return before, after

    idx = 0
    while debut + timedelta(weeks=idx) <= current + timedelta(weeks=1):
        ws = debut + timedelta(weeks=idx)
        we = ws + timedelta(days=7)
        ended = we <= today
        sp = spec_pace(ctx["vdot"], obj_pace, ctx["niveaux"]["specifique"])
        z = zones(ctx["vdot"], sp)
        z["fc"] = fc_ef
        forcee = ctx["allegee_next"]
        ctx["allegee_next"] = False
        if ws.isoformat() in frozen:
            sessions = copy.deepcopy(frozen[ws.isoformat()])
        else:
            sessions = P.generate_week(ws, idx, {"zones": z, "niveaux": dict(ctx["niveaux"]), "obj_pace": obj_pace,
                                                 "allegee_forcee": forcee}, cfg)
        for s in sessions:
            for k in ("statut", "analyse", "activite_id", "date_realisee", "ressenti"):
                s.pop(k, None)

        # --- association des sorties aux séances (dans l'ordre où tu les as faites) ---
        week_runs = [a for a in runs if ws <= act_date(a) < we]
        match, libres = {}, []
        for a in week_runs:
            laps = laps_by_id.get(str(a["activityId"]), [])
            free = [s for s in sessions if s["id"] not in match and not s.get("optionnelle")]
            dated = [s for s in free if s.get("date") == act_date(a).isoformat()]  # jour de course
            g = guess_type(a, laps, sessions)
            pick = dated[0] if dated else None
            if not pick and free:
                order = [g] + [t for t in ("petite", "longue", "allure") if t != g]
                for t in order:
                    pick = next((s for s in free if s["type"] == t and not s.get("date")), None)
                    if pick:
                        break
            if not pick:
                pick = next((s for s in sessions if s.get("optionnelle") and s["id"] not in match), None)
            if pick:
                match[pick["id"]] = a
            else:
                libres.append(summary(a) | {"date": act_date(a).isoformat()})

        # --- statut et analyse ---
        for s in sessions:
            a = match.get(s["id"])
            if a:
                s["statut"] = "faite"
                s["activite_id"] = a["activityId"]
                s["date_realisee"] = act_date(a).isoformat()
                s["analyse"] = analyze(s, a, laps_by_id.get(str(a["activityId"]), []))
                if ressentis.get(s["id"]):
                    s["ressenti"] = ressentis[s["id"]]
                serie = (series_by_id or {}).get(str(a["activityId"]))
                if serie:
                    s["analyse"]["serie"] = serie
            elif s.get("optionnelle"):
                s["statut"] = "facultative"
            elif ended:
                s["statut"] = "manquee"
            else:
                s["statut"] = "a_faire"

        # --- adaptation : séances faites dans l'ordre, puis manquées en fin de semaine ---
        done = sorted([s for s in sessions if s["statut"] == "faite"], key=lambda s: s["date_realisee"])
        missed = [s for s in sessions if s["statut"] == "manquee"]
        for s in done + missed:
            d = s.get("date_realisee") or (we - timedelta(days=1)).isoformat()
            nom = NOMS.get(s["sous_type"] if s["type"] == "allure" else s["type"], s["titre"])
            v = s.get("analyse", {}).get("verdict")
            st = s["sous_type"]
            if s["type"] == "bonus":
                continue
            if st in ("test", "course"):
                if v == "reussie":
                    before, after = set_vdot(max(s["analyse"]["vdot"], ctx["vdot"] - 1.0), d)
                    sens = "passe" if after < before else "s'ajuste"
                    log(d, f"{s['analyse']['resume'].split(' (')[0]} : ton niveau {sens} à {fmt_time(after)} sur 10 km. Toutes les allures sont mises à jour.",
                        "up" if after < before else "info")
                else:
                    log(d, "Test non trouvé : on garde les allures actuelles.", "hold")
            elif s["type"] == "allure":
                if s["statut"] == "manquee":
                    log(d, f"{nom} manquée : pas de rattrapage, la prochaine reste au même niveau.", "hold")
                elif v in ("reussie", "correcte") and s.get("ressenti") == "dur":
                    # allures tenues mais au prix d'un gros effort : on consolide avant de monter
                    ctx["bad"] = 0
                    log(d, f"{nom} tenue mais dure pour toi : on consolide au même niveau la prochaine fois.", "hold")
                elif v in ("reussie", "correcte"):
                    ctx["bad"] = 0
                    if not s.get("allegee"):
                        ctx["niveaux"][st] += 1
                        log(d, f"{nom} validée{' et facile pour toi' if s.get('ressenti') == 'facile' else ''} : la prochaine montera d'un cran.", "up")
                    # niveau estimé en continu à partir des fractions (seulement à la hausse)
                    tours = s["analyse"].get("tours") or []
                    if st in PCT and v == "reussie" and len(tours) >= 3:
                        est = vdot_from_pace(sum(t["allure_s"] for t in tours) / len(tours), PCT[st])
                        seuil_hausse = 0.15 if s.get("ressenti") == "facile" else 0.3  # facile = marge réelle
                        if est > ctx["vdot"] + seuil_hausse:
                            before, after = set_vdot(ctx["vdot"] + min(0.7, (est - ctx["vdot"]) / 2), d)
                            log(d, f"Tes fractions montrent que tu progresses : niveau estimé à {fmt_time(after)} sur 10 km, allures ajustées.", "up")
                else:
                    ctx["bad"] += 1
                    if ctx["bad"] >= 2:
                        ctx["bad"] = 0
                        ctx["allegee_next"] = True
                        ctx["niveaux"][st] = max(0, ctx["niveaux"][st] - 1)
                        log(d, "Deux séances dures difficiles d'affilée : la semaine suivante sera allégée.", "down")
                    else:
                        log(d, f"{nom} difficile : on reste au même niveau la prochaine fois.", "hold")
            else:
                if s["statut"] == "manquee":
                    log(d, f"{nom} manqué{'e' if s['type'] == 'longue' else ''} : pas de rattrapage, on reprend normalement.", "hold")
                elif v != "incomplete" and s.get("ressenti") == "dur":
                    log(d, f"{nom} faite mais dure pour toi : même durée la prochaine fois.", "hold")
                elif v != "incomplete" and not s.get("allegee"):
                    before = ctx["niveaux"][s["type"]]
                    ctx["niveaux"][s["type"]] += 1
                    table = P.LONGUE if s["type"] == "longue" else P.PETITE
                    if s["type"] == "longue" and P.lvl(table, before + 1) > P.lvl(table, before):
                        log(d, f"Sortie longue validée : {P.lvl(table, before + 1)} min la prochaine fois.", "up")

        if ended:
            keep = ("id", "type", "sous_type", "titre", "travail", "pourquoi", "reussite", "etapes", "semaine", "cycle",
                    "sem_cycle", "semaine_debut", "allegee", "optionnelle", "date", "duree_estimee_s", "distance_estimee_km")
            state.setdefault("semaines", {})[ws.isoformat()] = [{k: s[k] for k in keep if k in s} for s in sessions]

        main = [s for s in sessions if not s.get("optionnelle")]
        done_km = sum(s["analyse"]["realise"]["distance_km"] for s in sessions if s.get("analyse")) + \
            sum(l["distance_km"] for l in libres)
        weeks.append({
            "num": idx + 1, "cycle": idx // 4 + 1, "sem_cycle": idx % 4 + 1,
            "debut": ws.isoformat(), "fin": (we - timedelta(days=1)).isoformat(),
            "label": P.week_label(sessions), "allegee": any(s.get("allegee") for s in sessions),
            "km_prevus": round(sum(s["distance_estimee_km"] for s in main), 1),
            "km_faits": round(done_km, 1),
            "seances": sessions, "libres": libres,
        })
        idx += 1

    sp = spec_pace(ctx["vdot"], obj_pace, ctx["niveaux"]["specifique"])
    z = zones(ctx["vdot"], sp)
    pred = predict_time(ctx["vdot"], 10000)
    allures = {k: {"s": v, "texte": f"{fmt_pace(v[1])}–{fmt_pace(v[0])}"} for k, v in z.items()}
    if fc_ef:
        allures["ef"]["fc"] = fc_ef
    data = {
        "genere_le": datetime.now().isoformat(timespec="minutes"),
        "aujourdhui": today.isoformat(),
        "objectif": {"temps": obj["temps"], "distance_km": obj["distance_km"], "allure": fmt_pace(obj_pace), "s": obj_s},
        "niveau": {"vdot": round(ctx["vdot"], 1), "prediction": fmt_time(pred), "prediction_s": round(pred),
                   "depart_s": historique[0]["prediction_s"]},
        "fc_max": fcmax,
        "prenom": cfg.get("prenom"),
        "ville": cfg.get("ville"),
        "lieu": cfg.get("lieu"),
        "allures": allures,
        "semaines": weeks,
        "journal": list(reversed(journal)),
        "historique": historique,
        "date_course": cfg.get("date_course"),
    }
    return data, state
