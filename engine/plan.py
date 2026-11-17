"""Génération du plan : cycles de 4 semaines, 3 séances par semaine (petite, allure, longue)."""
from datetime import date, timedelta

from .paces import fmt_pace

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

# Progression de chaque type de séance (un cran = une séance réussie)
VMA = [(8, 400, 90), (10, 400, 90), (6, 600, 120), (8, 600, 120), (5, 800, 150), (6, 800, 150), (5, 1000, 180), (6, 1000, 180)]
SEUIL = [(3, 6, 2), (3, 8, 2), (4, 7, 2), (3, 10, 2), (4, 9, 2), (2, 15, 3), (3, 12, 2), (2, 20, 3)]  # fois, minutes, récup min
SPECIFIQUE = [(5, 1000, 90), (6, 1000, 90), (4, 1500, 120), (3, 2000, 120), (5, 1500, 120), (4, 2000, 120), (3, 3000, 150), (2, 4000, 180)]
LONGUE = [60, 65, 70, 75, 80, 85, 90]  # minutes
PETITE = [35, 40, 40, 45, 45]  # minutes

QUALITE = ["vma", "seuil", "specifique"]  # semaines 1, 2, 3 du cycle


def r(p):  # plage [lente, rapide] -> texte
    return f"{fmt_pace(p[1])}–{fmt_pace(p[0])}"


def lvl(table, n):
    return table[max(0, min(n, len(table) - 1))]


# ---------- étapes ----------
def st_time(kind, sec, zone=None, allure=None, label=None):
    return {"k": kind, "duree_s": int(sec), "zone": zone, "allure": allure, "label": label}


def st_dist(kind, m, zone=None, allure=None, label=None):
    return {"k": kind, "distance_m": int(m), "zone": zone, "allure": allure, "label": label}


def st_rep(n, steps):
    return {"k": "repeat", "fois": n, "etapes": steps}


def estimate(steps, z):
    """Durée (s) et distance (km) estimées."""
    ef_mid = (z["ef"][0] + z["ef"][1]) / 2
    dur = dist = 0.0
    for s in steps:
        if s["k"] == "repeat":
            d, km = estimate(s["etapes"], z)
            dur += d * s["fois"]
            dist += km * s["fois"]
            continue
        if s.get("allure"):
            pace = (s["allure"][0] + s["allure"][1]) / 2
        elif s["k"] == "recup":
            pace = ef_mid + 60
        elif s.get("zone") == "test":
            pace = z["vma"][0]
        else:
            pace = ef_mid
        if "duree_s" in s:
            dur += s["duree_s"]
            dist += s["duree_s"] / pace
        else:
            dist += s["distance_m"] / 1000
            dur += s["distance_m"] / 1000 * pace
    return dur, dist


# ---------- séances ----------
def ef_step(mins, z):
    st = st_time("continu", mins * 60, "ef", None if z.get("fc") else z["ef"], f"{mins} min en endurance")
    if z.get("fc"):
        st["fc"] = z["fc"]
    return st


def ef_target(z):
    return f"cardio entre {z['fc'][0]} et {z['fc'][1]} bpm" if z.get("fc") else f"allure entre {r(z['ef'])}/km"


def petite(n, z, allegee=False, bonus=False):
    mins = 30 if (allegee or bonus) else lvl(PETITE, n)
    with_strides = not allegee and not bonus and n >= 1
    steps = [ef_step(mins, z)]
    if with_strides:
        steps.append(st_rep(6, [st_time("effort", 20, "libre", None, "20 s vite et relâché"),
                                st_time("recup", 40, None, None, "40 s trot")]))
    return {
        "sous_type": "ef",
        "titre": "Footing + lignes droites" if with_strides else "Footing",
        "travail": "Endurance fondamentale : le fond (cœur, capillaires, tendons). C'est là que se fait l'essentiel de la progression."
        + (" Les lignes droites entretiennent une foulée rapide sans fatiguer." if with_strides else ""),
        "pourquoi": "Semaine allégée : on garde le rythme sans charger." if allegee
        else "Ajouter du volume facile entre les séances dures, et récupérer de la précédente.",
        "reussite": f"{ef_target(z).capitalize()}. Tu dois pouvoir parler en phrases complètes.",
        "etapes": steps,
    }


def longue(n, z, allegee=False):
    mins = 50 if allegee else lvl(LONGUE, n)
    return {
        "sous_type": "ef",
        "titre": "Sortie longue",
        "travail": "Endurance : pouvoir tenir 10 km à fond sans faiblir sur la fin.",
        "pourquoi": "Semaine allégée : sortie raccourcie, le corps assimile." if allegee
        else "Fin de semaine : on allonge un peu à chaque fois, toujours à allure facile.",
        "reussite": f"Régulier du début à la fin, {ef_target(z)}.",
        "etapes": [ef_step(mins, z)],
    }


def _intervals(warm, reps, cool):
    return [st_time("echauffement", warm * 60, "ef", None, f"{warm} min d'échauffement")] + reps + \
           [st_time("retour", cool * 60, "ef", None, f"{cool} min de retour au calme")]


def vma(n, z):
    fois, m, rec = lvl(VMA, n)
    return {
        "sous_type": "vma",
        "titre": f"VMA · {fois} × {m} m",
        "travail": "VMA : ta vitesse maximale en aérobie. Plus elle monte, plus l'allure 10 km devient facile.",
        "pourquoi": "Semaine 1 du cycle : tu es frais, c'est le moment de la séance la plus intense.",
        "reussite": f"Chaque fraction entre {r(z['vma'])}/km, la dernière aussi rapide que la première.",
        "etapes": _intervals(15, [st_rep(fois, [st_dist("effort", m, "vma", z["vma"], f"{m} m"),
                                               st_time("recup", rec, None, None, f"{rec // 60}:{rec % 60:02d} trot")])], 10),
    }


def seuil(n, z):
    fois, mins, rec = lvl(SEUIL, n)
    return {
        "sous_type": "seuil",
        "titre": f"Seuil · {fois} × {mins} min",
        "travail": "Seuil : l'allure la plus rapide que tu peux tenir longtemps. C'est le moteur du 10 km.",
        "pourquoi": "Semaine 2 du cycle : des efforts plus longs, un peu moins vite que la VMA.",
        "reussite": f"Blocs entre {r(z['seuil'])}/km, souffle contrôlé : tu peux encore dire quelques mots.",
        "etapes": _intervals(15, [st_rep(fois, [st_time("effort", mins * 60, "seuil", z["seuil"], f"{mins} min"),
                                               st_time("recup", rec * 60, None, None, f"{rec} min trot")])], 10),
    }


def specifique(n, z, obj_pace):
    fois, m, rec = lvl(SPECIFIQUE, n)
    return {
        "sous_type": "specifique",
        "titre": f"Allure 10 km · {fois} × {m / 1000:g} km",
        "travail": f"Allure 10 km : on se rapproche cycle après cycle de l'allure objectif ({fmt_pace(obj_pace)}/km).",
        "pourquoi": "Semaine 3 du cycle : on transforme la VMA et le seuil en vitesse de course.",
        "reussite": f"Fractions entre {r(z['specifique'])}/km. Plus vite ne sert à rien, on cherche la précision.",
        "etapes": _intervals(15, [st_rep(fois, [st_dist("effort", m, "specifique", z["specifique"], f"{m / 1000:g} km"),
                                               st_time("recup", rec, None, None, f"{rec // 60}:{rec % 60:02d} trot")])], 10),
    }


def test5k(z):
    return {
        "sous_type": "test",
        "titre": "Test 5 km",
        "travail": "Mesurer ton niveau pour recalculer toutes tes allures.",
        "pourquoi": "Semaine allégée : tu arrives reposé, le chrono sera fiable.",
        "reussite": "Premier km prudent, puis accélère. Après l'échauffement, appuie sur Tour pour lancer les 5 km.",
        "etapes": [{**st_time("echauffement", 15 * 60, "ef", None, "15 min d'échauffement, puis Tour"), "fin_tour": True},
                   st_dist("effort", 5000, "test", None, "5 km à fond"),
                   st_time("retour", 10 * 60, "ef", None, "10 min de retour au calme")],
    }


def rappel(z):
    s = specifique(0, z, (z["specifique"][0] + z["specifique"][1]) / 2)
    s["etapes"] = _intervals(15, [st_rep(3, [st_dist("effort", 1000, "specifique", z["specifique"], "1 km"),
                                            st_time("recup", 90, None, None, "1:30 trot")])], 10)
    s.update(titre="Rappel allure · 3 × 1 km", pourquoi="Semaine de course : on garde les sensations sans se fatiguer.",
             sous_type="specifique")
    return s


def course(z, dist_km):
    return {
        "sous_type": "course",
        "titre": f"Course · {dist_km:g} km",
        "travail": "Le jour J.",
        "pourquoi": "Tout le cycle mène ici.",
        "reussite": f"Pars à {fmt_pace(z['specifique'][0])}/km les 2 premiers km, puis cale-toi sur l'objectif.",
        "etapes": [{**st_time("echauffement", 15 * 60, "ef", None, "Échauffement, puis Tour au départ"), "fin_tour": True},
                   st_dist("effort", dist_km * 1000, "test", None, "Course")],
    }


# ---------- semaine ----------
SLOTS = ["petite", "allure", "longue"]  # pas de jours fixes : 3 séances à faire quand tu veux, + 1 bonus facultatif


def generate_week(week_start: date, idx: int, ctx: dict, cfg: dict) -> list:
    """ctx: niveaux, zones, obj_pace, allegee_forcee."""
    z, nv = ctx["zones"], ctx["niveaux"]
    sem = idx % 4 + 1
    cycle = idx // 4 + 1
    test_cycle = cycle % 2 == 1  # vrai test 5 km toutes les 8 semaines (cycles 1, 3, 5…)
    race = date.fromisoformat(cfg["date_course"]) if cfg.get("date_course") else None
    race_week = race and week_start <= race < week_start + timedelta(days=7)
    pre_race = race and week_start + timedelta(days=7) <= race < week_start + timedelta(days=14)
    allegee = sem == 4 or ctx.get("allegee_forcee") or pre_race

    sessions = []
    for slot in SLOTS:
        if race_week:
            if slot == "longue":
                continue
            s = petite(0, z, allegee=True) if slot == "petite" else rappel(z)
        elif slot == "petite":
            s = petite(nv["petite"], z, allegee)
        elif slot == "longue":
            s = longue(nv["longue"], z, allegee)
        elif sem == 4 and test_cycle and not ctx.get("allegee_forcee") and not pre_race:
            s = test5k(z)
        else:
            q = QUALITE[min(sem, 3) - 1]
            n = nv[q] - (1 if allegee else 0)
            s = {"vma": vma, "seuil": seuil}.get(q, lambda n, z: specifique(n, z, ctx["obj_pace"]))(n, z)
        s.update(id=f"{week_start.isoformat()}-{slot}", type=slot, optionnelle=False)
        sessions.append(s)
    if race_week:
        sessions.append({**course(z, cfg["objectif"]["distance_km"]), "id": f"{race.isoformat()}-course",
                         "type": "allure", "date": race.isoformat(), "optionnelle": False})
    elif not allegee:
        b = petite(0, z, bonus=True)
        b.update(id=f"{week_start.isoformat()}-bonus", type="bonus", optionnelle=True, titre="Footing bonus")
        sessions.append(b)
    for s in sessions:
        s.update(semaine=idx + 1, cycle=cycle, sem_cycle=sem, semaine_debut=week_start.isoformat(),
                 allegee=bool(allegee or race_week))
        dur, km = estimate(s["etapes"], z)
        s["duree_estimee_s"], s["distance_estimee_km"] = round(dur), round(km, 1)
    return sessions


def week_label(sessions) -> str:
    st = {s["sous_type"] for s in sessions}
    if "course" in st:
        return "Semaine de course"
    if "test" in st:
        return "Allégée + test"
    if any(s.get("allegee") for s in sessions):
        return "Allégée"
    q = next((s["sous_type"] for s in sessions if s["type"] == "allure"), None)
    return {"vma": "VMA", "seuil": "Seuil", "specifique": "Allure 10 km"}.get(q, "Semaine")
