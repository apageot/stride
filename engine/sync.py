"""Synchro Garmin : lit tes sorties, analyse, adapte le plan, envoie les prochaines séances.

    python -m engine.sync

Identifiants (variables d'environnement) :
    GARMIN_TOKENS_JSON  contenu du fichier garmin_tokens.json (créé par scripts/connexion_garmin.py)
    GARMIN_EMAIL / GARMIN_PASSWORD  en secours si les jetons ne marchent plus (sans double authentification)
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import build, is_run
from .garmin_format import to_garmin, workout_hash
from . import heat

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "state.json"
CACHE = ROOT / "state" / "activites.json"
DATA = ROOT / "docs" / "data.json"
TOKENS_DIR = Path(os.getenv("GARMIN_TOKENS_DIR", "~/.garminconnect")).expanduser()
LAP_KEYS = ("distance", "duration", "movingDuration", "averageSpeed", "averageHR", "maxHR", "intensityType", "wktStepIndex")
ACT_KEYS = ("activityId", "activityName", "startTimeLocal", "distance", "duration", "movingDuration", "averageSpeed",
            "averageHR", "maxHR", "activityType")


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def connect():
    from garminconnect import Garmin
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    tok = TOKENS_DIR / "garmin_tokens.json"
    if not tok.exists() and os.getenv("GARMIN_TOKENS_JSON"):
        tok.write_text(os.environ["GARMIN_TOKENS_JSON"])
        tok.chmod(0o600)
    g = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    g.login(str(TOKENS_DIR))
    return g


def _down(xs, n):
    if len(xs) <= n:
        return xs
    step = len(xs) / n
    return [xs[int(i * step)] for i in range(n)]


def parse_details(d: dict) -> dict:
    """Parcours GPS + courbes vitesse / altitude / cardio, allégés pour l'app."""
    out = {}
    # tracé GPS volontairement ignoré : rien de géolocalisé n'est publié
    idx = {m.get("key"): m.get("metricsIndex") for m in (d or {}).get("metricDescriptors", [])}
    rows = [r.get("metrics") or [] for r in (d or {}).get("activityDetailMetrics", [])]
    for key, name, nd in (("directSpeed", "vitesse", 2), ("directElevation", "altitude", 1), ("directHeartRate", "fc", 0)):
        i = idx.get(key)
        if i is None:
            continue
        vals = [r[i] for r in rows if i < len(r) and r[i] is not None]
        if len(vals) > 5:
            out[name] = [round(v, nd) for v in _down(vals, 140)]
    return out


def fetch(g, since: date, today: date, cache: dict):
    acts = g.get_activities_by_date(since.isoformat(), today.isoformat())
    known = {str(a["activityId"]) for a in cache["activities"]}
    for a in acts:
        if not is_run(a) or str(a["activityId"]) in known:
            continue
        slim = {k: a.get(k) for k in ACT_KEYS}
        # vie privée : on ne garde que le jour, pas l'heure (le dépôt est public)
        slim["startTimeLocal"] = (slim.get("startTimeLocal") or a.get("startTimeGMT") or "")[:10] + " 00:00:00"
        laps = g.get_activity_laps(a["activityId"]).get("lapDTOs", [])
        cache["laps"][str(a["activityId"])] = [{k: l.get(k) for k in LAP_KEYS} for l in laps]
        try:
            cache.setdefault("series", {})[str(a["activityId"])] = parse_details(g.get_activity_details(a["activityId"], maxchart=600, maxpoly=0))
        except Exception as e:
            print(f"  (détails GPS indisponibles : {e})")
        cache["activities"].append(slim)
        print(f"  + {slim['startTimeLocal']} {slim['activityName']} ({len(laps)} tours)")
    return cache


def push(g, data, state, today: date, wanted: str):
    """Envoie la séance demandée (bouton de l'app) et met à jour celles déjà envoyées si le plan a bougé.
    Une séance envoyée est placée dans ton calendrier Garmin à la date du jour."""
    sent = state.setdefault("garmin", {})
    week0 = (today - timedelta(days=today.weekday())).isoformat()
    live = {s["id"]: s for w in data["semaines"] if w["debut"] >= week0 for s in w["seances"] if s["statut"] != "faite"}
    targets = [sid for sid in live if sid in sent or sid == wanted]
    if wanted and wanted not in live:
        print(f"Séance {wanted} introuvable ou déjà faite")
    lieu = data.get("lieu") or {}
    for sid in targets:
        s = live[sid]
        w = to_garmin(s)
        h = workout_hash(w)  # empreinte du plan, hors météo
        if sid == wanted and lieu:
            # envoi demandé maintenant : on corrige les allures selon la chaleur du moment
            try:
                t = heat.temp_now(lieu["lat"], lieu["lon"])
                f = heat.factor(t)
                if f > 1:
                    s = dict(s, etapes=heat.adjust_steps(s["etapes"], f), titre=f"{s['titre']} · {round(t)}°")
                    w = to_garmin(s)
                    print(f"  chaleur {t:.0f}° ressentis : allures +{(f - 1) * 100:.0f} %")
            except Exception as e:
                print(f"  (météo indisponible : {e})")
        cur = sent.get(sid)
        if cur and cur["hash"] == h and sid != wanted:
            continue
        if cur:
            _delete(g, cur["workout_id"])
        wid = g.upload_workout(w)["workoutId"]
        g.schedule_workout(wid, today.isoformat())
        sent[sid] = {"workout_id": wid, "hash": h, "semaine": s["semaine_debut"]}
        print(f"  → Garmin : {s['titre']}")
    planned = {s["id"] for w in data["semaines"] for s in w["seances"]}
    for sid, cur in list(sent.items()):
        stale = cur["semaine"] >= week0 and sid not in planned          # plan modifié
        old = cur["semaine"] < (today - timedelta(days=28)).isoformat()  # ménage de la bibliothèque
        if stale or old:
            _delete(g, cur["workout_id"])
            del sent[sid]


def _delete(g, wid):
    try:
        g.delete_workout(wid)
    except Exception as e:  # déjà supprimée à la main, etc.
        print(f"  (suppression {wid} ignorée : {e})")


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    tz = ZoneInfo(cfg.get("fuseau", "Europe/Paris"))
    today = datetime.now(tz).date()
    state = load(STATE, {})
    cache = load(CACHE, {"activities": [], "laps": {}})
    debut = date.fromisoformat(cfg["debut"])
    erreur, g = None, None
    try:
        g = connect()
        cache = fetch(g, debut - timedelta(days=7), today, cache)
        # FC max : on regarde une fois tes 6 derniers mois (simples résumés, pas de détails)
        if "fc_hist" not in cache:
            old = g.get_activities_by_date((debut - timedelta(days=183)).isoformat(), debut.isoformat())
            cache["fc_hist"] = sorted(int(a["maxHR"]) for a in old
                                      if a.get("maxHR") and "running" in str((a.get("activityType") or {}).get("typeKey", "")))
    except Exception as e:
        erreur = f"Connexion Garmin impossible : {e}"
        print(erreur, file=sys.stderr)

    # mode choisi dans l'app : "aucune" = objectif seul, sinon date AAAA-MM-JJ
    dc = os.getenv("DATE_COURSE", "").strip()
    if dc:
        state["date_course"] = None if dc == "aucune" else date.fromisoformat(dc).isoformat()
    if "date_course" in state:
        cfg["date_course"] = state["date_course"]
    # ressenti envoyé depuis l'app : "id_séance=dur"
    r = os.getenv("RESSENTI", "").strip()
    if "=" in r:
        sid, val = r.split("=", 1)
        if val in ("facile", "ok", "dur"):
            state.setdefault("ressentis", {})[sid] = val
    hist = cache.get("fc_hist") or []
    if not cfg.get("fc_max") and len(hist) >= 3 and hist[-2] >= 150:
        cfg["fc_max"] = hist[-2]  # 2e plus haute valeur : on ignore un éventuel pic aberrant du capteur
    data, state = build(cfg, state, cache["activities"], cache["laps"], today, cache.get("series", {}))
    if g and not erreur:
        try:
            push(g, data, state, today, os.getenv("SEANCE", "").strip())
        except Exception as e:
            erreur = f"Envoi des séances à Garmin impossible : {e}"
            print(erreur, file=sys.stderr)
        try:
            g.client.dump(str(TOKENS_DIR))  # garde les jetons rafraîchis
        except Exception:
            pass
    data["garmin"] = {"derniere_synchro": datetime.now(tz).isoformat(timespec="minutes"),
                      "envoyees": sorted(state.get("garmin", {}))}
    if erreur:
        data["erreur"] = erreur
    save(STATE, state)
    save(CACHE, cache)
    save(DATA, data)
    print(f"OK — {sum(len(w['seances']) for w in data['semaines'])} séances, niveau {data['niveau']['prediction']} sur 10 km")


if __name__ == "__main__":
    main()
