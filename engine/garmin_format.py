"""Conversion d'une séance en séance structurée Garmin Connect (workout-service)."""
import hashlib
import json

RUN = {"sportTypeId": 1, "sportTypeKey": "running"}
STEP = {"echauffement": (1, "warmup"), "retour": (2, "cooldown"), "effort": (3, "interval"),
        "recup": (4, "recovery"), "continu": (3, "interval")}


def _speed(sec_per_km):
    return round(1000.0 / sec_per_km, 4)


def _step(s, order):
    tid, tkey = STEP[s["k"]]
    st = {"type": "ExecutableStepDTO", "stepOrder": order, "stepType": {"stepTypeId": tid, "stepTypeKey": tkey},
          "description": s.get("label") or ""}
    if s.get("fin_tour"):
        # l'étape se termine quand tu appuies sur Tour
        st["endCondition"] = {"conditionTypeId": 1, "conditionTypeKey": "lap.button"}
    elif "distance_m" in s:
        st["endCondition"] = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
        st["endConditionValue"] = float(s["distance_m"])
    else:
        st["endCondition"] = {"conditionTypeId": 2, "conditionTypeKey": "time"}
        st["endConditionValue"] = float(s["duree_s"])
    if s.get("fc"):
        st["targetType"] = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"}
        st["targetValueOne"] = float(s["fc"][0])
        st["targetValueTwo"] = float(s["fc"][1])
    elif s.get("allure"):
        slow, fast = s["allure"]
        st["targetType"] = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
        st["targetValueOne"] = _speed(slow)  # limite basse = allure la plus lente
        st["targetValueTwo"] = _speed(fast)
    else:
        st["targetType"] = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
    return st


def _steps(steps, counter):
    out = []
    for s in steps:
        counter[0] += 1
        if s["k"] == "repeat":
            order = counter[0]
            children = _steps(s["etapes"], counter)
            out.append({"type": "RepeatGroupDTO", "stepOrder": order,
                        "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                        "numberOfIterations": s["fois"], "smartRepeat": False,
                        "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
                        "endConditionValue": float(s["fois"]), "workoutSteps": children})
        else:
            out.append(_step(s, counter[0]))
    return out


def to_garmin(session: dict) -> dict:
    name = f"Stride · {session['titre']}"[:80]
    desc = f"{session['travail']}\nRéussie si : {session['reussite']}"[:1000]
    return {
        "workoutName": name,
        "description": desc,
        "sportType": RUN,
        "estimatedDurationInSecs": session.get("duree_estimee_s"),
        "workoutSegments": [{"segmentOrder": 1, "sportType": RUN, "workoutSteps": _steps(session["etapes"], [0])}],
    }


def workout_hash(w: dict) -> str:
    return hashlib.sha1(json.dumps(w, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
