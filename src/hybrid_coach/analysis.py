"""Pure functions that turn raw Garmin responses into compact coaching summaries.

Nothing here talks to Garmin or the database, so it is easy to test with fixtures.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

RUN_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "indoor_running", "virtual_run"}
HYBRID_TYPES = {"hiit", "strength_training", "indoor_cardio", "cardio", "obstacle_run", "obstacle_racing"}

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

READINESS_FACTORS = {
    "sleepScoreFactorFeedback": "last night's sleep",
    "sleepHistoryFactorFeedback": "sleep history",
    "recoveryTimeFactorFeedback": "recovery time",
    "acwrFactorFeedback": "acute load (load spike)",
    "stressHistoryFactorFeedback": "stress history",
    "hrvFactorFeedback": "HRV",
}


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


def kind(activity: dict) -> str:
    key = activity.get("activityType", {}).get("typeKey", "")
    if key in RUN_TYPES:
        return "run"
    if key in HYBRID_TYPES:
        return "hybrid"
    return "other"


def _day(activity: dict) -> str:
    return activity["startTimeLocal"][:10]


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


def is_hard(activity: dict) -> bool:
    return (activity.get("activityTrainingLoad") or 0) >= 100 or (activity.get("anaerobicTrainingEffect") or 0) >= 2.0


# --- readiness ---

def readiness(tr_entries: list[dict], sleep: dict, hrv: dict, summary: dict,
              recent_activities: list[dict], now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"date": now.date().isoformat(), "missing": []}
    cautions: list[str] = []
    stop = False

    tr = max(tr_entries, key=lambda x: x.get("timestampLocal") or "") if tr_entries else None
    if tr:
        limiting = [label for k, label in READINESS_FACTORS.items() if tr.get(k) == "POOR"]
        limiting += [f"{label} (moderate)" for k, label in READINESS_FACTORS.items() if tr.get(k) == "MODERATE"]
        out["garmin_readiness"] = {
            "score": tr.get("score"), "level": tr.get("level"),
            "garmin_says": tr.get("feedbackShort"), "limiting_factors": limiting,
        }
        out["recovery_hours_left"] = round((tr.get("recoveryTime") or 0) / 60)
        out["acute_load"] = tr.get("acuteLoad")
        if tr.get("level") == "POOR":
            stop = True
            cautions.append(f"Garmin readiness is POOR ({tr.get('score')})")
        elif tr.get("level") == "LOW":
            cautions.append(f"Garmin readiness is LOW ({tr.get('score')})")
        if out["recovery_hours_left"] > 24:
            cautions.append(f"{out['recovery_hours_left']}h of recovery time left")
        if tr.get("acwrFactorFeedback") == "POOR":
            cautions.append("acute load is spiking vs your usual load")
    else:
        out["missing"].append("Garmin training readiness (watch may not support it, or no sync yet today)")

    dto = sleep.get("dailySleepDTO") or {}
    score = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    if dto.get("sleepTimeSeconds"):
        out["sleep"] = {"score": score, "hours": round(dto["sleepTimeSeconds"] / 3600, 1),
                        "deep_h": round((dto.get("deepSleepSeconds") or 0) / 3600, 1),
                        "rem_h": round((dto.get("remSleepSeconds") or 0) / 3600, 1)}
        if score is not None and score < 60:
            cautions.append(f"poor sleep score ({score})")
    else:
        out["missing"].append("last night's sleep")

    hs = hrv.get("hrvSummary") or {}
    if hs:
        base = hs.get("baseline") or {}
        out["hrv"] = {"last_night": hs.get("lastNightAvg"), "weekly_avg": hs.get("weeklyAvg"),
                      "baseline_range": [base.get("balancedLow"), base.get("balancedUpper")],
                      "status": hs.get("status")}
        if hs.get("status") in ("LOW", "POOR", "UNBALANCED"):
            cautions.append(f"HRV status {hs['status']} (weekly avg {hs.get('weeklyAvg')} vs baseline "
                            f"{base.get('balancedLow')}-{base.get('balancedUpper')})")
    else:
        out["missing"].append("overnight HRV")

    rhr, rhr7 = summary.get("restingHeartRate"), summary.get("lastSevenDaysAvgRestingHeartRate")
    if rhr:
        out["resting_hr"] = {"today": rhr, "avg_7d": rhr7}
        if rhr7 and rhr >= rhr7 + 5:
            cautions.append(f"resting HR elevated ({rhr} vs {rhr7} 7-day avg)")
    if summary.get("bodyBatteryMostRecentValue") is not None:
        out["body_battery"] = {"now": summary.get("bodyBatteryMostRecentValue"),
                               "peak_today": summary.get("bodyBatteryHighestValue")}

    hard = sorted((a for a in recent_activities if is_hard(a)), key=lambda a: a["startTimeLocal"])
    if hard:
        last = hard[-1]
        hours_ago = (now - datetime.fromisoformat(last["startTimeLocal"])).total_seconds() / 3600
        out["last_hard_session"] = {"date": _day(last), "name": last.get("activityName"),
                                    "type": last["activityType"]["typeKey"], "hours_ago": round(hours_ago),
                                    "load": round(last.get("activityTrainingLoad") or 0)}
        if hours_ago < 24:
            cautions.append(f"hard session {round(hours_ago)}h ago ({last.get('activityName')})")

    if stop or len(cautions) >= 3:
        out["signal"] = "rest_or_very_easy"
    elif cautions:
        out["signal"] = "easy"
    else:
        out["signal"] = "ready_for_hard"
    out["reasons"] = cautions or ["no recovery red flags"]
    return out


# --- Garmin Coach ---

def coach_plan(plan: dict | None, today: date, days_ahead: int, activities_since_start: list[dict]) -> dict[str, Any]:
    if not plan:
        return {"has_plan": False,
                "hint": "No active Garmin Coach plan. The coach will plan runs from history instead."}

    start = date.fromisoformat(plan["startDate"][:10])
    phases = plan.get("adaptivePlanPhases") or []
    current = next((p["trainingPhase"] for p in phases if p.get("currentPhase")), None)
    event = next((p["startDate"] for p in phases if p.get("trainingPhase") == "TARGET_EVENT_DAY"), None)

    upcoming = []
    horizon = (today + timedelta(days=days_ahead)).isoformat()
    for t in plan.get("taskList") or []:
        if not (today.isoformat() <= t["calendarDate"] <= horizon):
            continue
        w = t.get("taskWorkout") or {}
        if w.get("restDay"):
            upcoming.append({"date": t["calendarDate"], "workout": "Rest"})
            continue
        upcoming.append({
            "date": t["calendarDate"],
            "workout": w.get("workoutName"),
            "target": w.get("workoutDescription"),
            "est_minutes": round((w.get("estimatedDurationInSecs") or 0) / 60),
            "est_km": round((w.get("estimatedDistanceInMeters") or 0) / 1000, 1),
            "key_workout": t.get("keyWorkout", False),
            "status": w.get("adaptiveCoachingWorkoutStatus"),
        })

    weeks_elapsed = max((today - start).days, 0) / 7
    runs_done = sum(1 for a in activities_since_start if kind(a) == "run" and _day(a) >= start.isoformat())
    return {
        "has_plan": True,
        "name": plan.get("name"),
        "level": (plan.get("trainingLevel") or {}).get("levelKey"),
        "start": start.isoformat(),
        "event_date": event,
        "days_to_event": (date.fromisoformat(event) - today).days if event else None,
        "week": f"{int(weeks_elapsed) + 1} of {plan.get('durationInWeeks')}",
        "phase": current,
        "phases": [{"phase": p["trainingPhase"], "from": p["startDate"], "to": p["endDate"]} for p in phases],
        "today": next((u for u in upcoming if u["date"] == today.isoformat()), None),
        "upcoming": [u for u in upcoming if u["date"] != today.isoformat()],
        "consistency": {"runs_since_start": runs_done,
                        "expected_approx": round(weeks_elapsed * (plan.get("avgWeeklyWorkouts") or 0))},
    }


# --- training summary ---

def training_summary(activities: list[dict], weeks: int, today: date, training_status: dict) -> dict[str, Any]:
    monday = today - timedelta(days=today.weekday())
    buckets: dict[str, dict] = {}
    for i in range(weeks - 1, -1, -1):
        wk = (monday - timedelta(weeks=i)).isoformat()
        buckets[wk] = {"week_of": wk, "run_km": 0.0, "runs": 0, "hybrid_sessions": 0, "other_sessions": 0,
                       "hours": 0.0, "load": 0.0, "hard_sessions": 0}
    for a in activities:
        d = date.fromisoformat(_day(a))
        wk = (d - timedelta(days=d.weekday())).isoformat()
        b = buckets.get(wk)
        if b is None:
            continue
        k = kind(a)
        if k == "run":
            b["runs"] += 1
            b["run_km"] += (a.get("distance") or 0) / 1000
        elif k == "hybrid":
            b["hybrid_sessions"] += 1
        else:
            b["other_sessions"] += 1
        b["hours"] += (a.get("duration") or 0) / 3600
        b["load"] += a.get("activityTrainingLoad") or 0
        b["hard_sessions"] += is_hard(a)
    rows = [{**b, "run_km": round(b["run_km"], 1), "hours": round(b["hours"], 1), "load": round(b["load"])}
            for b in buckets.values()]

    out: dict[str, Any] = {"weeks": rows}
    lb = (training_status.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {}
    dev = next((v for v in lb.values() if v.get("primaryTrainingDevice")), None) or next(iter(lb.values()), None)
    if dev:
        out["load_balance_4wk"] = {
            "feedback": dev.get("trainingBalanceFeedbackPhrase"),
            "aerobic_low": [round(dev["monthlyLoadAerobicLow"]), dev.get("monthlyLoadAerobicLowTargetMin"), dev.get("monthlyLoadAerobicLowTargetMax")],
            "aerobic_high": [round(dev["monthlyLoadAerobicHigh"]), dev.get("monthlyLoadAerobicHighTargetMin"), dev.get("monthlyLoadAerobicHighTargetMax")],
            "anaerobic": [round(dev["monthlyLoadAnaerobic"]), dev.get("monthlyLoadAnaerobicTargetMin"), dev.get("monthlyLoadAnaerobicTargetMax")],
            "format": "[actual, target_min, target_max]",
        }
    status = (training_status.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    dev_status = next(iter(status.values()), None)
    if dev_status:
        acute = dev_status.get("acuteTrainingLoadDTO") or {}
        out["training_status"] = {"garmin_status": dev_status.get("trainingStatusFeedbackPhrase"),
                                  "acute_chronic_ratio": acute.get("dailyAcuteChronicWorkloadRatio"),
                                  "acwr_status": acute.get("acwrStatus")}
    return out


def session_rows(activities: list[dict], noted_ids: set[int], noted_days: set[str]) -> list[dict]:
    rows = []
    for a in sorted(activities, key=lambda a: a["startTimeLocal"], reverse=True):
        rows.append({
            "activity_id": a["activityId"], "date": _day(a), "name": a.get("activityName"),
            "type": a["activityType"]["typeKey"], "minutes": round((a.get("duration") or 0) / 60),
            "km": round((a.get("distance") or 0) / 1000, 1) or None,
            "pace": pace(a.get("averageSpeed")) if kind(a) == "run" else None,
            "avg_hr": a.get("averageHR"), "load": round(a.get("activityTrainingLoad") or 0),
            "has_note": a["activityId"] in noted_ids or (kind(a) == "hybrid" and _day(a) in noted_days),
        })
    return rows


# --- progress ---

def _series_change(points: list[tuple[str, float]], lower_is_better: bool = False) -> dict | None:
    points = sorted(p for p in points if p[1] is not None)
    if not points:
        return None
    (d0, v0), (d1, v1) = points[0], points[-1]
    return {"from": {"date": d0, "value": v0}, "to": {"date": d1, "value": v1},
            "verdict": _change(v0, v1, lower_is_better)}


def aerobic_efficiency(activities: list[dict], max_hr: float) -> list[tuple[str, float]]:
    """Metres covered per heartbeat on easy runs: rises as aerobic fitness improves."""
    pts = []
    for a in activities:
        if kind(a) != "run" or not a.get("averageHR") or not a.get("averageSpeed"):
            continue
        if a["averageHR"] > max_hr or (a.get("duration") or 0) < 15 * 60:
            continue
        pts.append((_day(a), round(a["averageSpeed"] * 60 / a["averageHR"], 3)))
    return pts


def progress(activities: list[dict], predictions: list[dict], endurance: dict, hill: dict,
             lactate: dict, tolerance: list[dict], notes: list[dict]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    missing: list[str] = []

    vo2 = _series_change([(_day(a), a.get("vO2MaxValue")) for a in activities if kind(a) == "run"])
    if vo2:
        metrics["vo2max"] = vo2

    if predictions:
        for key, label in [("time5K", "5k"), ("time10K", "10k"), ("timeHalfMarathon", "half_marathon")]:
            ch = _series_change([(p["calendarDate"], p.get(key)) for p in predictions], lower_is_better=True)
            if ch:
                ch["from"]["value"], ch["to"]["value"] = hms(ch["from"]["value"]), hms(ch["to"]["value"])
                metrics[f"predicted_{label}"] = ch
    else:
        missing.append("race predictions")

    groups = endurance.get("groupMap") or {}
    if groups:
        ch = _series_change([(d, g.get("groupAverage")) for d, g in groups.items()])
        cur = (endurance.get("enduranceScoreDTO") or {})
        score = cur.get("overallScore") or ch["to"]["value"]
        ch["level_now"] = next(label for floor, label in ENDURANCE_CLASSES if score >= floor)
        # Contributor ids: activity type 180 is HIIT; group 0 covers running activities.
        names = {180: "hiit", 3: "hiking", 25: "indoor_cycling", 30: "elliptical"}
        contrib = {}
        for c in cur.get("contributors") or []:
            label = names.get(c.get("activityTypeId"), f"type_{c.get('activityTypeId')}") if c.get("activityTypeId") \
                else ("running" if c.get("group") == 0 else "other")
            contrib[label] = round(c["contribution"])
        ch["contribution_pct"] = contrib
        metrics["endurance_score"] = ch

    hills = hill.get("hillScoreDTOList") or []
    if hills:
        metrics["hill_score"] = _series_change([(h["calendarDate"], h.get("overallScore")) for h in hills])

    lt = lactate.get("speed_and_heart_rate") or {}
    ftp = lactate.get("power") or {}
    if lt.get("heartRate"):
        # Garmin reports threshold speed in tens of m/s (0.325 -> 3.25 m/s).
        metrics["lactate_threshold"] = {"hr": lt["heartRate"], "pace": pace((lt.get("speed") or 0) * 10),
                                        "running_ftp_w": ftp.get("functionalThresholdPower"),
                                        "as_of": (lt.get("calendarDate") or "")[:10]}
    lt_hr = lt.get("heartRate") or 170
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

    if tolerance:
        recent = sorted(tolerance, key=lambda t: t["calendarDate"])[-3:]
        metrics["running_impact_vs_tolerance"] = [
            {"week_of": t["startOfWeek"], "impact_load": t["totalImpactLoad"], "tolerance": t["tolerance"],
             "pct_of_tolerance": round(100 * t["totalImpactLoad"] / t["tolerance"]) if t.get("tolerance") else None}
            for t in recent
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
