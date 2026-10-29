"""Garmin Connect provider: maps Garmin's raw responses into the normalized models."""

from datetime import date, datetime

from ...models import (
    Activity, CoachPlan, EnduranceScore, HrvDay, ImpactWeek, LactateThreshold, LoadBalance,
    PerformanceMetrics, PlanPhase, PlannedWorkout, Prediction, ProviderReadiness, SleepNight, Vitals,
)
from ...store import Store
from ..base import Capabilities
from .api import GarminData

READINESS_FACTORS = {
    "sleepScoreFactorFeedback": "last night's sleep",
    "sleepHistoryFactorFeedback": "sleep history",
    "recoveryTimeFactorFeedback": "recovery time",
    "acwrFactorFeedback": "acute load (load spike)",
    "stressHistoryFactorFeedback": "stress history",
    "hrvFactorFeedback": "HRV",
}

# Endurance-score contributor ids Garmin reports for non-running activity types.
CONTRIBUTOR_NAMES = {180: "hiit", 3: "hiking", 25: "indoor_cycling", 30: "elliptical"}


def map_activity(a: dict) -> Activity:
    return Activity(
        id=a["activityId"],
        start=datetime.fromisoformat(a["startTimeLocal"]),
        name=a.get("activityName"),
        sport_key=(a.get("activityType") or {}).get("typeKey", ""),
        duration_s=a.get("duration") or 0.0,
        distance_m=a.get("distance") or 0.0,
        avg_hr=a.get("averageHR"),
        max_hr=a.get("maxHR"),
        avg_speed_mps=a.get("averageSpeed"),
        load=a.get("activityTrainingLoad"),
        anaerobic_te=a.get("anaerobicTrainingEffect"),
        vo2max=a.get("vO2MaxValue"),
    )


def map_readiness(entries: list[dict]) -> ProviderReadiness | None:
    if not entries:
        return None
    tr = max(entries, key=lambda x: x.get("timestampLocal") or "")
    return ProviderReadiness(
        score=tr.get("score"), level=tr.get("level"), feedback=tr.get("feedbackShort"),
        factor_ratings={label: tr[key] for key, label in READINESS_FACTORS.items() if tr.get(key)},
        recovery_hours=(tr.get("recoveryTime") or 0) / 60, acute_load=tr.get("acuteLoad"), source="garmin",
    )


def map_sleep(raw: dict, day: str) -> SleepNight | None:
    dto = raw.get("dailySleepDTO") or {}
    if not dto.get("sleepTimeSeconds"):
        return None
    return SleepNight(
        day=day, total_s=dto["sleepTimeSeconds"], deep_s=dto.get("deepSleepSeconds") or 0,
        rem_s=dto.get("remSleepSeconds") or 0,
        score=((dto.get("sleepScores") or {}).get("overall") or {}).get("value"),
    )


def map_hrv(raw: dict, day: str) -> HrvDay | None:
    s = raw.get("hrvSummary")
    if not s:
        return None
    base = s.get("baseline") or {}
    return HrvDay(day=day, last_night=s.get("lastNightAvg"), weekly_avg=s.get("weeklyAvg"),
                  baseline_low=base.get("balancedLow"), baseline_high=base.get("balancedUpper"),
                  status=s.get("status"), method="rmssd")


def map_vitals(raw: dict, day: str) -> Vitals | None:
    if not raw:
        return None
    return Vitals(day=day, resting_hr=raw.get("restingHeartRate"),
                  resting_hr_7d=raw.get("lastSevenDaysAvgRestingHeartRate"),
                  body_battery_now=raw.get("bodyBatteryMostRecentValue"),
                  body_battery_peak=raw.get("bodyBatteryHighestValue"))


def map_load_balance(raw: dict) -> LoadBalance | None:
    lb = (raw.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {}
    dev = next((v for v in lb.values() if v.get("primaryTrainingDevice")), None) or next(iter(lb.values()), None)
    if not dev:
        return None
    status = (raw.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    st = next(iter(status.values()), {}) or {}
    acute = st.get("acuteTrainingLoadDTO") or {}

    def bucket(name: str) -> list[float | None]:
        v = dev.get(f"monthlyLoad{name}")
        return [round(v) if v is not None else None, dev.get(f"monthlyLoad{name}TargetMin"),
                dev.get(f"monthlyLoad{name}TargetMax")]

    return LoadBalance(
        feedback=dev.get("trainingBalanceFeedbackPhrase"), aerobic_low=bucket("AerobicLow"),
        aerobic_high=bucket("AerobicHigh"), anaerobic=bucket("Anaerobic"),
        status=st.get("trainingStatusFeedbackPhrase"),
        acute_chronic_ratio=acute.get("dailyAcuteChronicWorkloadRatio"), acwr_status=acute.get("acwrStatus"),
    )


def map_coach_plan(raw: dict | None) -> CoachPlan | None:
    if not raw:
        return None
    workouts = []
    for t in raw.get("taskList") or []:
        w = t.get("taskWorkout") or {}
        if w.get("restDay"):
            workouts.append(PlannedWorkout(day=t["calendarDate"], rest=True))
            continue
        workouts.append(PlannedWorkout(
            day=t["calendarDate"], name=w.get("workoutName"), target=w.get("workoutDescription"),
            est_minutes=round((w.get("estimatedDurationInSecs") or 0) / 60),
            est_km=round((w.get("estimatedDistanceInMeters") or 0) / 1000, 1),
            key_workout=bool(t.get("keyWorkout")), status=w.get("adaptiveCoachingWorkoutStatus"),
        ))
    return CoachPlan(
        name=raw.get("name"), level=(raw.get("trainingLevel") or {}).get("levelKey"),
        start=date.fromisoformat(raw["startDate"][:10]), duration_weeks=raw.get("durationInWeeks"),
        avg_weekly_workouts=raw.get("avgWeeklyWorkouts") or 0,
        phases=[PlanPhase(p["trainingPhase"], p["startDate"], p["endDate"], bool(p.get("currentPhase")))
                for p in raw.get("adaptivePlanPhases") or []],
        workouts=workouts,
    )


def map_endurance(raw: dict) -> EnduranceScore | None:
    groups = raw.get("groupMap") or {}
    if not groups:
        return None
    series = sorted((d, g["groupAverage"]) for d, g in groups.items() if g.get("groupAverage") is not None)
    dto = raw.get("enduranceScoreDTO") or {}
    contributions = {}
    for c in dto.get("contributors") or []:
        if c.get("activityTypeId"):
            label = CONTRIBUTOR_NAMES.get(c["activityTypeId"], f"type_{c['activityTypeId']}")
        else:
            label = "running" if c.get("group") == 0 else "other"
        contributions[label] = round(c["contribution"])
    return EnduranceScore(series=series, current=dto.get("overallScore"), contributions=contributions)


def map_lactate(raw: dict) -> LactateThreshold | None:
    lt = raw.get("speed_and_heart_rate") or {}
    if not lt.get("heartRate"):
        return None
    speed = lt.get("speed")
    return LactateThreshold(
        hr=lt["heartRate"],
        # Garmin reports threshold speed in tens of m/s (0.325 -> 3.25 m/s).
        speed_mps=speed * 10 if speed else None,
        ftp_w=(raw.get("power") or {}).get("functionalThresholdPower"),
        as_of=(lt.get("calendarDate") or "")[:10],
    )


class GarminProvider:
    name = "garmin"
    label = "Garmin Connect"
    capabilities = Capabilities(sleep=True, hrv=True, vitals=True, readiness=True, load_balance=True,
                                coach_plan=True, performance=True)

    def __init__(self, store: Store, data: GarminData | None = None):
        self.data = data or GarminData(store)

    def activities(self, start: str, end: str) -> list[Activity]:
        return [map_activity(a) for a in self.data.activities(start, end)]

    def sleep(self, day: str) -> SleepNight | None:
        return map_sleep(self.data.sleep(day), day)

    def hrv(self, day: str) -> HrvDay | None:
        return map_hrv(self.data.hrv(day), day)

    def vitals(self, day: str) -> Vitals | None:
        return map_vitals(self.data.user_summary(day), day)

    def readiness(self, day: str) -> ProviderReadiness | None:
        return map_readiness(self.data.training_readiness(day))

    def load_balance(self, day: str) -> LoadBalance | None:
        return map_load_balance(self.data.training_status(day))

    def coach_plan(self) -> CoachPlan | None:
        return map_coach_plan(self.data.coach_plan())

    def performance(self, start: str, end: str) -> PerformanceMetrics:
        preds = [Prediction(day=p["calendarDate"], t5k=p.get("time5K"), t10k=p.get("time10K"),
                            half=p.get("timeHalfMarathon")) for p in self.data.race_predictions(start, end)]
        hills = (self.data.hill_score(start, end).get("hillScoreDTOList") or [])
        tolerance = sorted(self.data.running_tolerance(start, end), key=lambda t: t["startOfWeek"])
        return PerformanceMetrics(
            predictions=preds,
            endurance=map_endurance(self.data.endurance_score(start, end)),
            hill_series=[(h["calendarDate"], h["overallScore"]) for h in hills if h.get("overallScore") is not None],
            lactate=map_lactate(self.data.lactate_threshold()),
            impact=[ImpactWeek(t["startOfWeek"], t["totalImpactLoad"], t["tolerance"]) for t in tolerance],
        )

    def check(self, day: str, start: str) -> list[tuple[str, str]]:
        d = self.data
        checks = {
            "training readiness": lambda: d.training_readiness(day),
            "sleep": lambda: d.sleep(day),
            "hrv": lambda: d.hrv(day),
            "daily summary": lambda: d.user_summary(day),
            "activities (28d)": lambda: d.activities(start, day),
            "training status": lambda: d.training_status(day),
            "garmin coach plan": lambda: d.coach_plan(),
            "endurance score": lambda: d.endurance_score(start, day),
            "hill score": lambda: d.hill_score(start, day),
            "race predictions": lambda: d.race_predictions(start, day),
            "running tolerance": lambda: d.running_tolerance(start, day),
            "lactate threshold": lambda: d.lactate_threshold(),
        }
        out = []
        for label, fn in checks.items():
            try:
                status = "ok" if fn() else "empty (not supported by your watch or no data yet)"
            except Exception as e:
                status = f"FAILED {type(e).__name__}: {str(e)[:80]}"
            out.append((label, status))
        return out
