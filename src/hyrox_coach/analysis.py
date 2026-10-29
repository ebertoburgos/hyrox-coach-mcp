"""Pure functions that turn normalized models into compact coaching summaries.

Nothing here talks to a provider or the database, so it is easy to test with plain objects.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from .models import (
    Activity, CoachPlan, HrvDay, LoadBalance, PerformanceMetrics, ProviderReadiness, SleepNight, Vitals,
)

STATIONS = ["skierg", "sled_push", "sled_pull", "burpee_broad_jumps", "row", "farmers_carry", "sandbag_lunges", "wall_balls"]
STATION_ALIASES = {
    "ski": "skierg", "ski erg": "skierg", "skierg": "skierg",
    "sled push": "sled_push", "push": "sled_push",
    "sled pull": "sled_pull", "pull": "sled_pull",
    "burpee": "burpee_broad_jumps", "burpees": "burpee_broad_jumps", "bbj": "burpee_broad_jumps",
    "burpee broad jump": "burpee_broad_jumps", "burpee broad jumps": "burpee_broad_jumps",
    "row": "row", "rowing": "row", "rower": "row",
    "farmers": "farmers_carry", "farmer carry": "farmers_carry", "farmers carry": "farmers_carry",
    "lunges": "sandbag_lunges", "sandbag lunge": "sandbag_lunges", "sandbag lunges": "sandbag_lunges",
    "wall ball": "wall_balls", "wall balls": "wall_balls", "wallballs": "wall_balls",
}

# Race-format standards per division. Weights are the commonly published ones;
# the athlete should confirm against their event's current rulebook.
RACE_FORMAT = {
    "stations": {
        "skierg": "1000 m", "sled_push": "50 m", "sled_pull": "50 m", "burpee_broad_jumps": "80 m",
        "row": "1000 m", "farmers_carry": "200 m", "sandbag_lunges": "100 m", "wall_balls": "100 reps",
    },
    "divisions": {
        "open_men": {"sled_push": "152 kg", "sled_pull": "103 kg", "farmers_carry": "2x24 kg",
                     "sandbag_lunges": "20 kg", "wall_balls": "6 kg to 3 m"},
        "open_women": {"sled_push": "102 kg", "sled_pull": "78 kg", "farmers_carry": "2x16 kg",
                       "sandbag_lunges": "10 kg", "wall_balls": "4 kg to 2.7 m"},
        "pro_men": {"sled_push": "202 kg", "sled_pull": "153 kg", "farmers_carry": "2x32 kg",
                    "sandbag_lunges": "30 kg", "wall_balls": "9 kg to 3 m"},
        "pro_women": {"sled_push": "152 kg", "sled_pull": "103 kg", "farmers_carry": "2x24 kg",
                      "sandbag_lunges": "20 kg", "wall_balls": "6 kg to 2.7 m"},
    },
}

ENDURANCE_CLASSES = [(8600, "elite"), (7900, "superior"), (7200, "expert"), (6500, "well trained"),
                     (5800, "trained"), (5100, "intermediate"), (0, "recreational")]


# --- formatting helpers ---

def hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def pace(m_per_s: float | None) -> str | None:
    if not m_per_s:
        return None
    return f"{hms(1000 / m_per_s)}/km"


def _change(start: float | None, now: float | None, lower_is_better: bool = False, tolerance: float = 0.01) -> str:
    if start is None or now is None:
        return "not enough data"
    if start == 0:
        return "stable"
    rel = (now - start) / abs(start)
    if lower_is_better:
        rel = -rel
    if rel > tolerance:
        return "improving"
    if rel < -tolerance:
        return "declining"
    return "stable"


def normalize_station(name: str) -> str:
    key = name.strip().lower().replace("_", " ").replace("-", " ")
    return STATION_ALIASES.get(key, key.replace(" ", "_"))


def is_hard(a: Activity) -> bool:
    return (a.load or 0) >= 100 or (a.anaerobic_te or 0) >= 2.0


# --- readiness ---

def readiness(provider_readiness: ProviderReadiness | None, sleep: SleepNight | None, hrv: HrvDay | None,
              vitals: Vitals | None, recent: list[Activity], now: datetime, provider_label: str = "provider",
              ) -> dict[str, Any]:
    out: dict[str, Any] = {"date": now.date().isoformat(), "missing": []}
    cautions: list[str] = []
    stop = False

    pr = provider_readiness
    if pr:
        limiting = [k for k, v in pr.factor_ratings.items() if v == "POOR"]
        limiting += [f"{k} (moderate)" for k, v in pr.factor_ratings.items() if v == "MODERATE"]
        out["provider_readiness"] = {"source": pr.source, "score": pr.score, "level": pr.level,
                                     "says": pr.feedback, "limiting_factors": limiting}
        out["recovery_hours_left"] = round(pr.recovery_hours or 0)
        out["acute_load"] = pr.acute_load
        if pr.level == "POOR":
            stop = True
            cautions.append(f"{provider_label} readiness is POOR ({pr.score})")
        elif pr.level == "LOW":
            cautions.append(f"{provider_label} readiness is LOW ({pr.score})")
        if out["recovery_hours_left"] > 24:
            cautions.append(f"{out['recovery_hours_left']}h of recovery time left")
        if pr.factor_ratings.get("acute load (load spike)") == "POOR":
            cautions.append("acute load is spiking vs your usual load")
    else:
        out["missing"].append(f"readiness score ({provider_label} does not supply one, or no data yet today)")

    if sleep:
        out["sleep"] = {"score": sleep.score, "hours": round(sleep.total_s / 3600, 1),
                        "deep_h": round(sleep.deep_s / 3600, 1), "rem_h": round(sleep.rem_s / 3600, 1)}
        if sleep.score is not None and sleep.score < 60:
            cautions.append(f"poor sleep score ({sleep.score})")
    else:
        out["missing"].append("last night's sleep")

    if hrv:
        out["hrv"] = {"last_night": hrv.last_night, "weekly_avg": hrv.weekly_avg,
                      "baseline_range": [hrv.baseline_low, hrv.baseline_high], "status": hrv.status,
                      "method": hrv.method}
        if hrv.status in ("LOW", "POOR", "UNBALANCED"):
            cautions.append(f"HRV status {hrv.status} (weekly avg {hrv.weekly_avg} vs baseline "
                            f"{hrv.baseline_low}-{hrv.baseline_high})")
    else:
        out["missing"].append("overnight HRV")

    if vitals:
        if vitals.resting_hr:
            out["resting_hr"] = {"today": vitals.resting_hr, "avg_7d": vitals.resting_hr_7d}
            if vitals.resting_hr_7d and vitals.resting_hr >= vitals.resting_hr_7d + 5:
                cautions.append(f"resting HR elevated ({vitals.resting_hr} vs {vitals.resting_hr_7d} 7-day avg)")
        if vitals.body_battery_now is not None:
            out["body_battery"] = {"now": vitals.body_battery_now, "peak_today": vitals.body_battery_peak}

    hard = sorted((a for a in recent if is_hard(a)), key=lambda a: a.start)
    if hard:
        last = hard[-1]
        hours_ago = (now - last.start).total_seconds() / 3600
        out["last_hard_session"] = {"date": last.day, "name": last.name, "type": last.sport_key,
                                    "hours_ago": round(hours_ago), "load": round(last.load or 0)}
        if hours_ago < 24:
            cautions.append(f"hard session {round(hours_ago)}h ago ({last.name})")

    if stop or len(cautions) >= 3:
        out["signal"] = "rest_or_very_easy"
    elif cautions:
        out["signal"] = "easy"
    else:
        out["signal"] = "ready_for_hard"
    out["reasons"] = cautions or ["no recovery red flags"]
    return out


# --- coach plan ---

def coach_plan(plan: CoachPlan | None, today: date, days_ahead: int, activities: list[Activity]) -> dict[str, Any]:
    if not plan:
        return {"has_plan": False,
                "hint": "No active coach plan from this provider. Plan runs from training history instead."}

    horizon = (today + timedelta(days=days_ahead)).isoformat()
    window = [w for w in plan.workouts if today.isoformat() <= w.day <= horizon]

    def row(w) -> dict:
        if w.rest:
            return {"date": w.day, "workout": "Rest"}
        return {"date": w.day, "workout": w.name, "target": w.target, "est_minutes": w.est_minutes,
                "est_km": w.est_km, "key_workout": w.key_workout, "status": w.status}

    weeks_elapsed = max((today - plan.start).days, 0) / 7
    runs_done = sum(1 for a in activities if a.kind == "run" and a.day >= plan.start.isoformat())
    event = plan.event_date
    return {
        "has_plan": True,
        "name": plan.name,
        "level": plan.level,
        "start": plan.start.isoformat(),
        "event_date": event,
        "days_to_event": (date.fromisoformat(event) - today).days if event else None,
        "week": f"{int(weeks_elapsed) + 1} of {plan.duration_weeks}",
        "phase": plan.current_phase,
        "phases": [{"phase": p.phase, "from": p.start, "to": p.end} for p in plan.phases],
        "today": next((row(w) for w in window if w.day == today.isoformat()), None),
        "upcoming": [row(w) for w in window if w.day != today.isoformat()],
        "consistency": {"runs_since_start": runs_done,
                        "expected_approx": round(weeks_elapsed * plan.avg_weekly_workouts)},
    }


# --- training summary ---

def training_summary(activities: list[Activity], weeks: int, today: date, load: LoadBalance | None) -> dict[str, Any]:
    monday = today - timedelta(days=today.weekday())
    buckets: dict[str, dict] = {}
    for i in range(weeks - 1, -1, -1):
        wk = (monday - timedelta(weeks=i)).isoformat()
        buckets[wk] = {"week_of": wk, "run_km": 0.0, "runs": 0, "hybrid_sessions": 0, "other_sessions": 0,
                       "hours": 0.0, "load": 0.0, "hard_sessions": 0}
    for a in activities:
        d = a.start.date()
        b = buckets.get((d - timedelta(days=d.weekday())).isoformat())
        if b is None:
            continue
        if a.kind == "run":
            b["runs"] += 1
            b["run_km"] += a.distance_m / 1000
        elif a.kind == "hybrid":
            b["hybrid_sessions"] += 1
        else:
            b["other_sessions"] += 1
        b["hours"] += a.duration_s / 3600
        b["load"] += a.load or 0
        b["hard_sessions"] += is_hard(a)
    rows = [{**b, "run_km": round(b["run_km"], 1), "hours": round(b["hours"], 1), "load": round(b["load"])}
            for b in buckets.values()]

    out: dict[str, Any] = {"weeks": rows}
    if load:
        out["load_balance_4wk"] = {"feedback": load.feedback, "aerobic_low": load.aerobic_low,
                                   "aerobic_high": load.aerobic_high, "anaerobic": load.anaerobic,
                                   "format": "[actual, target_min, target_max]"}
        out["training_status"] = {"status": load.status, "acute_chronic_ratio": load.acute_chronic_ratio,
                                  "acwr_status": load.acwr_status}
    return out


def session_rows(activities: list[Activity], noted_ids: set[int], noted_days: set[str]) -> list[dict]:
    return [{
        "activity_id": a.id, "date": a.day, "name": a.name, "type": a.sport_key,
        "minutes": round(a.duration_s / 60), "km": round(a.distance_m / 1000, 1) or None,
        "pace": pace(a.avg_speed_mps) if a.kind == "run" else None,
        "avg_hr": a.avg_hr, "load": round(a.load or 0),
        "has_note": a.id in noted_ids or (a.kind == "hybrid" and a.day in noted_days),
    } for a in sorted(activities, key=lambda a: a.start, reverse=True)]


# --- progress ---

def _series_change(points: list[tuple[str, float | None]], lower_is_better: bool = False) -> dict | None:
    points = sorted(p for p in points if p[1] is not None)
    if not points:
        return None
    (d0, v0), (d1, v1) = points[0], points[-1]
    return {"from": {"date": d0, "value": v0}, "to": {"date": d1, "value": v1},
            "verdict": _change(v0, v1, lower_is_better)}


def aerobic_efficiency(activities: list[Activity], max_hr: float) -> list[tuple[str, float]]:
    """Metres covered per heartbeat on easy runs: rises as aerobic fitness improves."""
    pts = []
    for a in activities:
        if a.kind != "run" or not a.avg_hr or not a.avg_speed_mps:
            continue
        if a.avg_hr > max_hr or a.duration_s < 15 * 60:
            continue
        pts.append((a.day, round(a.avg_speed_mps * 60 / a.avg_hr, 3)))
    return pts


def progress(activities: list[Activity], perf: PerformanceMetrics, notes: list[dict]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    missing: list[str] = []

    vo2 = _series_change([(a.day, a.vo2max) for a in activities if a.kind == "run"])
    if vo2:
        metrics["vo2max"] = vo2

    if perf.predictions:
        for attr, label in [("t5k", "5k"), ("t10k", "10k"), ("half", "half_marathon")]:
            ch = _series_change([(p.day, getattr(p, attr)) for p in perf.predictions], lower_is_better=True)
            if ch:
                ch["from"]["value"], ch["to"]["value"] = hms(ch["from"]["value"]), hms(ch["to"]["value"])
                metrics[f"predicted_{label}"] = ch
    else:
        missing.append("race predictions (not supplied by this provider, or no data yet)")

    end = perf.endurance
    if end and end.series:
        ch = _series_change(end.series)
        score = end.current or ch["to"]["value"]
        ch["level_now"] = next(label for floor, label in ENDURANCE_CLASSES if score >= floor)
        ch["contribution_pct"] = end.contributions
        metrics["endurance_score"] = ch

    hill = _series_change(perf.hill_series)
    if hill:
        metrics["hill_score"] = hill

    lt_hr = 170
    if perf.lactate:
        lt = perf.lactate
        lt_hr = lt.hr
        metrics["lactate_threshold"] = {"hr": lt.hr, "pace": pace(lt.speed_mps), "running_ftp_w": lt.ftp_w,
                                        "as_of": lt.as_of}
    eff = aerobic_efficiency(activities, max_hr=lt_hr * 0.88)
    if len(eff) >= 4:
        eff.sort()
        half = len(eff) // 2
        early = sum(v for _, v in eff[:half]) / half
        late = sum(v for _, v in eff[half:]) / (len(eff) - half)
        metrics["aerobic_efficiency"] = {
            "meaning": "metres per heartbeat on easy runs (higher = fitter)",
            "early_avg": round(early, 3), "recent_avg": round(late, 3),
            "runs_used": len(eff), "verdict": _change(early, late, tolerance=0.02),
        }
    else:
        missing.append("easy runs for aerobic efficiency (need 4+)")

    if perf.impact:
        metrics["running_impact_vs_tolerance"] = [
            {"week_of": w.week_of, "impact_load": w.impact_load, "tolerance": w.tolerance,
             "pct_of_tolerance": round(100 * w.impact_load / w.tolerance) if w.tolerance else None}
            for w in perf.impact[-3:]
        ]

    stations: dict[str, list[dict]] = defaultdict(list)
    for n in notes:
        for s in n["stations"]:
            stations[s["station"]].append({"date": n["date"], **{k: v for k, v in s.items() if k != "station" and v is not None}})
    if stations:
        metrics["stations"] = {k: {"sessions_logged": len(v), "first": v[0], "latest": v[-1]} for k, v in stations.items()}
    not_logged = [s for s in STATIONS if s not in stations]
    if not_logged:
        missing.append(f"no logged station work for: {', '.join(not_logged)}")

    return {"metrics": metrics, "missing": missing}


# --- race profile ---

def race_phase(race_date: date, today: date, coach_phases: list[dict] | None = None) -> str:
    for p in coach_phases or []:
        if p["from"] <= today.isoformat() <= p["to"]:
            return p["phase"].lower()
    days = (race_date - today).days
    if days < 0:
        return "post_race"
    if days == 0:
        return "race_day"
    if days <= 7:
        return "taper"
    if days <= 21:
        return "peak"
    return "build"
