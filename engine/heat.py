"""Allures corrigées de la chaleur.

Au-dessus de ~15 °C ressentis, le corps dépense de l'énergie à se refroidir : à effort égal on court
moins vite. Règle simple et prudente : +0,5 % de temps au km par °C au-dessus de 15 °C (plafond +10 %).
Les séances pilotées au cardio (endurance) n'ont pas besoin de correction : le cardio intègre déjà la chaleur.
"""
import copy
import json
import urllib.request

BASE_C, PAR_DEGRE, PLAFOND = 15.0, 0.005, 0.10


def factor(temp_c):
    if temp_c is None or temp_c <= BASE_C:
        return 1.0
    return 1.0 + min(PLAFOND, PAR_DEGRE * (temp_c - BASE_C))


def adjust_steps(steps, f):
    out = copy.deepcopy(steps)
    for st in out:
        if st.get("k") == "repeat":
            st["etapes"] = adjust_steps(st["etapes"], f)
        elif st.get("allure"):
            st["allure"] = [round(st["allure"][0] * f), round(st["allure"][1] * f)]
    return out


def temp_now(lat, lon, timeout=8):
    """Température ressentie : la plus haute entre maintenant et les 3 prochaines heures (Open-Meteo, sans clé)."""
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=apparent_temperature&hourly=apparent_temperature&forecast_hours=3&timezone=auto")
    with urllib.request.urlopen(url, timeout=timeout) as r:
        j = json.load(r)
    vals = [j.get("current", {}).get("apparent_temperature")] + (j.get("hourly", {}).get("apparent_temperature") or [])
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None
