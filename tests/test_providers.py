"""Provider layer: Garmin mapping, registry, config and the legacy-folder migration."""

import importlib
from datetime import date

import pytest

from hyrox_coach import config, store as store_mod
from hyrox_coach.providers import ProviderUnavailable, get_provider
from hyrox_coach.providers import garmin as g


def test_map_activity_and_kind():
    a = g.map_activity({"activityId": 7, "startTimeLocal": "2026-10-29 09:10:00", "activityName": "Long Run",
                        "activityType": {"typeKey": "treadmill_running"}, "duration": 3000.0, "distance": 7000.0,
                        "averageHR": 136.0, "averageSpeed": 2.3, "activityTrainingLoad": 72.0, "vO2MaxValue": 48.0})
    assert (a.id, a.day, a.kind, a.load, a.vo2max) == (7, "2026-10-29", "run", 72.0, 48.0)
    assert g.map_activity({"activityId": 8, "startTimeLocal": "2026-10-27 18:41:32",
                           "activityType": {"typeKey": "hiit"}}).kind == "hybrid"


def test_map_readiness_picks_latest_and_labels_factors():
    r = g.map_readiness([
        {"timestampLocal": "2026-10-29T06:00:00", "level": "HIGH", "score": 80},
        {"timestampLocal": "2026-10-29T10:02:34", "level": "LOW", "score": 46, "feedbackShort": "TAKE_IT_EASY",
         "hrvFactorFeedback": "POOR", "sleepScoreFactorFeedback": "MODERATE", "recoveryTime": 1257, "acuteLoad": 465},
    ])
    assert r.score == 46 and r.factor_ratings == {"HRV": "POOR", "last night's sleep": "MODERATE"}
    assert round(r.recovery_hours) == 21
    assert g.map_readiness([]) is None


def test_map_sleep_hrv_vitals():
    s = g.map_sleep({"dailySleepDTO": {"sleepTimeSeconds": 23280, "deepSleepSeconds": 7380,
                                       "sleepScores": {"overall": {"value": 76}}}}, "2026-10-29")
    assert s.score == 76 and s.deep_s == 7380
    assert g.map_sleep({}, "2026-10-29") is None
    h = g.map_hrv({"hrvSummary": {"lastNightAvg": 41, "weeklyAvg": 40, "status": "LOW",
                                  "baseline": {"balancedLow": 44, "balancedUpper": 59}}}, "2026-10-29")
    assert (h.baseline_low, h.baseline_high, h.method) == (44, 59, "rmssd")
    assert g.map_hrv({}, "2026-10-29") is None
    v = g.map_vitals({"restingHeartRate": 51, "lastSevenDaysAvgRestingHeartRate": 52,
                      "bodyBatteryMostRecentValue": 48}, "2026-10-29")
    assert (v.resting_hr, v.resting_hr_7d, v.body_battery_now) == (51, 52, 48)


def test_map_lactate_converts_speed():
    lt = g.map_lactate({"speed_and_heart_rate": {"heartRate": 167, "speed": 0.325,
                                                 "calendarDate": "2026-10-28T17:23:53.177"},
                        "power": {"functionalThresholdPower": 378}})
    assert lt.hr == 167 and round(lt.speed_mps, 2) == 3.25 and lt.ftp_w == 378 and lt.as_of == "2026-10-28"
    assert g.map_lactate({}) is None


def test_map_coach_plan():
    plan = g.map_coach_plan({
        "name": "Race Plan", "startDate": "2026-10-19T00:00:00.0", "durationInWeeks": 6, "avgWeeklyWorkouts": 4,
        "trainingLevel": {"levelKey": "Beginner"},
        "adaptivePlanPhases": [{"trainingPhase": "BUILD", "startDate": "2026-10-19", "endDate": "2026-11-08",
                                "currentPhase": True},
                               {"trainingPhase": "TARGET_EVENT_DAY", "startDate": "2026-11-30", "endDate": "2026-11-30"}],
        "taskList": [{"calendarDate": "2026-10-31", "keyWorkout": True,
                      "taskWorkout": {"workoutName": "Threshold", "workoutDescription": "4x4:00@5:05/km",
                                      "estimatedDurationInSecs": 2520, "estimatedDistanceInMeters": 7147}},
                     {"calendarDate": "2026-10-30", "taskWorkout": {"restDay": True}}]})
    assert plan.start == date(2026, 10, 19) and plan.event_date == "2026-11-30" and plan.current_phase == "BUILD"
    assert [w.rest for w in plan.workouts] == [False, True] and plan.workouts[0].est_km == 7.1
    assert g.map_coach_plan(None) is None


def test_map_endurance_contributors():
    e = g.map_endurance({"groupMap": {"2026-10-16": {"groupAverage": 5300}, "2026-10-23": {"groupAverage": 5397}},
                         "enduranceScoreDTO": {"overallScore": 5414, "contributors": [
                             {"activityTypeId": None, "group": 0, "contribution": 47.5},
                             {"activityTypeId": 180, "group": None, "contribution": 45.55}]}})
    assert e.series[-1] == ("2026-10-23", 5397) and e.contributions == {"running": 48, "hiit": 46}


def test_registry_unknown_and_planned_provider(tmp_path):
    st = store_mod.Store(tmp_path / "t.db")
    with pytest.raises(ProviderUnavailable, match="coming soon"):
        get_provider("apple_health", st)
    with pytest.raises(ProviderUnavailable, match="Available now: garmin"):
        get_provider("nope", st)
    assert get_provider("garmin", st).capabilities.coach_plan is True


def test_config_provider_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.delenv("HYROX_COACH_PROVIDER", raising=False)
    assert config.provider_name() == "garmin"
    (tmp_path / "config.toml").write_text('provider = "apple_health"\n')
    assert config.provider_name() == "apple_health"
    monkeypatch.setenv("HYROX_COACH_PROVIDER", "garmin")
    assert config.provider_name() == "garmin"


def test_legacy_home_is_copied_once(tmp_path, monkeypatch):
    monkeypatch.delenv("HYROX_COACH_HOME", raising=False)
    monkeypatch.delenv("HYBRID_COACH_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy = tmp_path / ".hybrid-coach"
    legacy.mkdir()
    (legacy / "coach.db").write_text("notes")
    home = store_mod._home()
    assert home == tmp_path / ".hyrox-coach" and (home / "coach.db").read_text() == "notes"
    assert (legacy / "coach.db").exists()  # copied, not moved
    (legacy / "coach.db").write_text("changed later")
    store_mod._home()
    assert (home / "coach.db").read_text() == "notes"  # never overwritten
    importlib.reload(store_mod)
