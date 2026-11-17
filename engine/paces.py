"""Allures d'entraînement calculées à partir d'un chrono (formules VDOT de Jack Daniels)."""
import math


def parse_time(s: str) -> int:
    """'22:30' ou '1:02:30' -> secondes."""
    parts = [int(p) for p in s.strip().split(":")]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_pace(sec_per_km: float) -> str:
    sec = int(round(sec_per_km))
    return f"{sec // 60}:{sec % 60:02d}"


def vdot_from_race(distance_m: float, time_s: float) -> float:
    t = time_s / 60.0
    v = distance_m / t  # m/min
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    pct = 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)
    return vo2 / pct


def _speed_at(vdot: float, pct: float) -> float:
    """Vitesse (m/min) correspondant à un % de VO2max."""
    target = vdot * pct
    a, b, c = 0.000104, 0.182258, -(4.60 + target)
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def pace_at(vdot: float, pct: float) -> float:
    """Allure en s/km pour un % de VO2max."""
    return 60000.0 / _speed_at(vdot, pct)


def predict_time(vdot: float, distance_m: float) -> float:
    """Temps prédit (s) sur une distance pour un VDOT donné (bissection)."""
    lo, hi = 60.0, 6 * 3600.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if vdot_from_race(distance_m, mid) > vdot:
            lo = mid  # trop rapide -> temps plus long
        else:
            hi = mid
    return (lo + hi) / 2


def zones(vdot: float, spec_pace: float) -> dict:
    """Plages d'allure [lente, rapide] en s/km. spec_pace = allure cible des séances allure 10 km."""
    return {
        "ef": [round(pace_at(vdot, 0.595)), round(pace_at(vdot, 0.635))],
        "seuil": [round(pace_at(vdot, 0.86)), round(pace_at(vdot, 0.89))],
        "vma": [round(pace_at(vdot, 0.955)), round(pace_at(vdot, 0.995))],
        "specifique": [round(spec_pace + 3), round(spec_pace - 3)],
    }


def best_vdot(records: dict) -> float:
    dist = {"5km": 5000, "10km": 10000, "semi": 21097.5, "3km": 3000}
    vals = [vdot_from_race(dist[k], parse_time(v)) for k, v in records.items() if k in dist and v]
    return max(vals)


def vdot_from_pace(sec_per_km: float, pct: float) -> float:
    """VDOT qui correspond à une allure tenue à un % de VO2max (bissection)."""
    lo, hi = 20.0, 90.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if pace_at(mid, pct) > sec_per_km:
            lo = mid  # allure calculée trop lente -> VDOT plus haut
        else:
            hi = mid
    return (lo + hi) / 2
