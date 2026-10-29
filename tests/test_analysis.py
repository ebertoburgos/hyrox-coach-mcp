"""Analysis tests on small synthetic fixtures (no real athlete data in the repo)."""

from datetime import date, datetime

from hybrid_coach import analysis


def act(day, type_key="running", load=60, anaerobic=0.0, hr=140, speed=2.8, minutes=40, km=6.0, vo2=None, aid=1):
    return {"activityId": aid, "startTimeLocal": f"{day} 09:00:00", "activityName": type_key,
            "activityType": {"typeKey": type_key}, "activityTrainingLoad": load,
            "anaerobicTrainingEffect": anaerobic, "averageHR": hr, "averageSpeed": speed,
            "duration": minutes * 60, "distance": km * 1000, "vO2MaxValue": vo2}


def readiness_entry(level="HIGH", score=80, **factors):
    return {"timestampLocal": "2026-10-29T07:00:00.0", "level": level, "score": score,
            "feedbackShort": "READY", "recoveryTime": 120, "acuteLoad": 300, **factors}


HRV_BALANCED = {"hrvSummary": {"lastNightAvg": 50, "weeklyAvg": 50, "status": "BALANCED",
                               "baseline": {"balancedLow": 44, "balancedUpper": 59}}}
SLEEP_OK = {"dailySleepDTO": {"sleepTimeSeconds": 8 * 3600, "sleepScores": {"overall": {"value": 85}}}}
NOW = datetime(2026, 10, 29, 12, 0)


def test_readiness_ready_when_no_flags():
    out = analysis.readiness([readiness_entry()], SLEEP_OK, HRV_BALANCED,
                             {"restingHeartRate": 50, "lastSevenDaysAvgRestingHeartRate": 51}, [], NOW)
    assert out["signal"] == "ready_for_hard"
    assert out["missing"] == []


def test_readiness_easy_after_hard_session_and_low_hrv():
    hrv = {"hrvSummary": {**HRV_BALANCED["hrvSummary"], "status": "LOW"}}
    hard = act("2026-10-28", "hiit", load=130)
    hard["startTimeLocal"] = "2026-10-28 19:00:00"
    out = analysis.readiness([readiness_entry(hrvFactorFeedback="POOR")], SLEEP_OK, hrv, {}, [hard], NOW)
    assert out["signal"] == "easy"
    assert "HRV" in out["garmin_readiness"]["limiting_factors"]
    assert any("hard session 17h ago" in r for r in out["reasons"])


def test_readiness_rest_when_garmin_poor_and_reports_missing():
    out = analysis.readiness([readiness_entry(level="POOR", score=15)], {}, {}, {}, [], NOW)
    assert out["signal"] == "rest_or_very_easy"
    assert "last night's sleep" in out["missing"]


def test_coach_plan_today_upcoming_and_phase():
    plan = {
        "name": "Race Plan", "startDate": "2026-10-19T00:00:00.0", "durationInWeeks": 6, "avgWeeklyWorkouts": 4,
        "adaptivePlanPhases": [
            {"startDate": "2026-10-19", "endDate": "2026-11-08", "trainingPhase": "BUILD", "currentPhase": True},
            {"startDate": "2026-11-30", "endDate": "2026-11-30", "trainingPhase": "TARGET_EVENT_DAY", "currentPhase": False},
        ],
        "taskList": [
            {"calendarDate": "2026-10-29", "keyWorkout": True,
             "taskWorkout": {"workoutName": "Long Run", "workoutDescription": "138bpm",
                             "estimatedDurationInSecs": 3120, "estimatedDistanceInMeters": 8320}},
            {"calendarDate": "2026-10-30", "taskWorkout": {"restDay": True}},
            {"calendarDate": "2026-11-10", "taskWorkout": {"workoutName": "Too far ahead"}},
        ],
    }
    out = analysis.coach_plan(plan, date(2026, 10, 29), 3, [act("2026-10-20"), act("2026-10-10")])
    assert out["phase"] == "BUILD" and out["week"] == "2 of 6"
    assert out["days_to_event"] == 32
    assert out["today"]["workout"] == "Long Run" and out["today"]["est_km"] == 8.3
    assert out["upcoming"] == [{"date": "2026-10-30", "workout": "Rest"}]
    assert out["consistency"]["runs_since_start"] == 1


def test_coach_plan_absent():
    assert analysis.coach_plan(None, date(2026, 10, 29), 7, [])["has_plan"] is False


def test_training_summary_buckets_by_week():
    acts = [act("2026-10-27", km=5), act("2026-10-28", "hiit", load=120, km=0), act("2026-10-21", km=8)]
    weeks = analysis.training_summary(acts, 2, date(2026, 10, 29), {})["weeks"]
    assert [w["week_of"] for w in weeks] == ["2026-10-19", "2026-10-26"]
    assert weeks[1]["run_km"] == 5.0 and weeks[1]["hybrid_sessions"] == 1 and weeks[1]["hard_sessions"] == 1
    assert weeks[0]["run_km"] == 8.0


def test_progress_predictions_lower_is_better_and_station_trends():
    preds = [{"calendarDate": "2026-08-01", "time5K": 1640}, {"calendarDate": "2026-10-29", "time5K": 1550}]
    notes = [{"date": "2026-10-20", "stations": [{"station": "sled_push", "weight_kg": 100}]},
             {"date": "2026-10-27", "stations": [{"station": "sled_push", "weight_kg": 125}]}]
    out = analysis.progress([], preds, {}, {}, {}, [], notes)
    p5 = out["metrics"]["predicted_5k"]
    assert p5["verdict"] == "improving" and p5["to"]["value"] == "25:50"
    assert out["metrics"]["stations"]["sled_push"]["latest"]["weight_kg"] == 125
    assert any("wall_balls" in m for m in out["missing"])


def test_aerobic_efficiency_skips_hard_and_short_runs():
    acts = [act("2026-10-01", hr=130), act("2026-10-02", hr=175), act("2026-10-03", hr=130, minutes=10),
            act("2026-10-04", "hiit", hr=130)]
    pts = analysis.aerobic_efficiency(acts, max_hr=147)
    assert pts == [("2026-10-01", round(2.8 * 60 / 130, 3))]


def test_lactate_threshold_speed_conversion():
    out = analysis.progress([], [], {}, {}, {"speed_and_heart_rate": {"heartRate": 167, "speed": 0.325}}, [], [])
    assert out["metrics"]["lactate_threshold"]["pace"] == "5:08/km"


def test_normalize_station_and_race_phase():
    assert analysis.normalize_station("Wall Balls") == "wall_balls"
    assert analysis.normalize_station("sled-push") == "sled_push"
    assert analysis.normalize_station("Box jumps") == "box_jumps"
    assert analysis.race_phase(date(2026, 11, 30), date(2026, 11, 25)) == "taper"
    phases = [{"phase": "PEAK", "from": "2026-11-09", "to": "2026-11-22"}]
    assert analysis.race_phase(date(2026, 11, 30), date(2026, 11, 10), phases) == "peak"
