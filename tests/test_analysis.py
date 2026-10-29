"""Analysis tests on small synthetic models (no real athlete data in the repo)."""

from datetime import date, datetime

from hyrox_coach import analysis
from hyrox_coach.models import (
    Activity, CoachPlan, EnduranceScore, HrvDay, ImpactWeek, LactateThreshold, LoadBalance,
    PerformanceMetrics, PlanPhase, PlannedWorkout, Prediction, ProviderReadiness, SleepNight, Vitals,
)

NOW = datetime(2026, 10, 29, 12, 0)


def act(day, sport="running", load=60, anaerobic=0.0, hr=140, speed=2.8, minutes=40, km=6.0, vo2=None,
        aid=1, time="09:00:00"):
    return Activity(id=aid, start=datetime.fromisoformat(f"{day} {time}"), name=sport, sport_key=sport,
                    duration_s=minutes * 60, distance_m=km * 1000, avg_hr=hr, avg_speed_mps=speed,
                    load=load, anaerobic_te=anaerobic, vo2max=vo2)


def ready(level="HIGH", score=80, **ratings):
    return ProviderReadiness(score=score, level=level, feedback="READY", factor_ratings=ratings,
                             recovery_hours=2, acute_load=300, source="test")


HRV_OK = HrvDay("2026-10-29", 50, 50, 44, 59, "BALANCED", "rmssd")
SLEEP_OK = SleepNight("2026-10-29", 8 * 3600, 7200, 5400, score=85)
VITALS_OK = Vitals("2026-10-29", 50, 51)


def test_readiness_ready_when_no_flags():
    out = analysis.readiness(ready(), SLEEP_OK, HRV_OK, VITALS_OK, [], NOW)
    assert out["signal"] == "ready_for_hard"
    assert out["missing"] == []


def test_readiness_easy_after_hard_session_and_low_hrv():
    hrv = HrvDay("2026-10-29", 41, 40, 44, 59, "LOW", "rmssd")
    hard = act("2026-10-28", "hiit", load=130, time="19:00:00")
    out = analysis.readiness(ready(**{"HRV": "POOR"}), SLEEP_OK, hrv, None, [hard], NOW)
    assert out["signal"] == "easy"
    assert "HRV" in out["provider_readiness"]["limiting_factors"]
    assert any("hard session 17h ago" in r for r in out["reasons"])


def test_readiness_rest_when_provider_poor_and_reports_missing():
    out = analysis.readiness(ready(level="POOR", score=15), None, None, None, [], NOW)
    assert out["signal"] == "rest_or_very_easy"
    assert "last night's sleep" in out["missing"]


def test_readiness_without_provider_score_still_works_and_says_so():
    out = analysis.readiness(None, SLEEP_OK, HRV_OK, VITALS_OK, [], NOW, provider_label="Apple Health")
    assert out["signal"] == "ready_for_hard"
    assert any("Apple Health does not supply" in m for m in out["missing"])
    assert out["hrv"]["method"] == "rmssd"


def plan():
    return CoachPlan(
        name="Race Plan", level="Beginner", start=date(2026, 10, 19), duration_weeks=6, avg_weekly_workouts=4,
        phases=[PlanPhase("BUILD", "2026-10-19", "2026-11-08", True),
                PlanPhase("TARGET_EVENT_DAY", "2026-11-30", "2026-11-30")],
        workouts=[PlannedWorkout("2026-10-29", "Long Run", "138bpm", 52, 8.3, True, "COMPLETED_VIA_ACTIVITY"),
                  PlannedWorkout("2026-10-30", rest=True),
                  PlannedWorkout("2026-11-10", "Too far ahead")])


def test_coach_plan_today_upcoming_and_phase():
    out = analysis.coach_plan(plan(), date(2026, 10, 29), 3, [act("2026-10-20"), act("2026-10-10")])
    assert out["phase"] == "BUILD" and out["week"] == "2 of 6"
    assert out["days_to_event"] == 32
    assert out["today"]["workout"] == "Long Run" and out["today"]["est_km"] == 8.3
    assert out["upcoming"] == [{"date": "2026-10-30", "workout": "Rest"}]
    assert out["consistency"]["runs_since_start"] == 1


def test_coach_plan_absent():
    assert analysis.coach_plan(None, date(2026, 10, 29), 7, [])["has_plan"] is False


def test_training_summary_buckets_by_week_and_load_balance():
    acts = [act("2026-10-27", km=5), act("2026-10-28", "hiit", load=120, km=0), act("2026-10-21", km=8)]
    lb = LoadBalance("ON_TARGET", [700, 327, 722], [442, 382, 696], [230, 0, 327], "PRODUCTIVE", 1.2, "OPTIMAL")
    out = analysis.training_summary(acts, 2, date(2026, 10, 29), lb)
    weeks = out["weeks"]
    assert [w["week_of"] for w in weeks] == ["2026-10-19", "2026-10-26"]
    assert weeks[1]["run_km"] == 5.0 and weeks[1]["hybrid_sessions"] == 1 and weeks[1]["hard_sessions"] == 1
    assert weeks[0]["run_km"] == 8.0
    assert out["load_balance_4wk"]["feedback"] == "ON_TARGET" and out["training_status"]["acute_chronic_ratio"] == 1.2


def test_training_summary_without_load_balance():
    assert "load_balance_4wk" not in analysis.training_summary([], 1, date(2026, 10, 29), None)


def test_progress_predictions_lower_is_better_and_station_trends():
    perf = PerformanceMetrics(predictions=[Prediction("2026-08-01", t5k=1640), Prediction("2026-10-29", t5k=1550)])
    notes = [{"date": "2026-10-20", "stations": [{"station": "sled_push", "weight_kg": 100}]},
             {"date": "2026-10-27", "stations": [{"station": "sled_push", "weight_kg": 125}]}]
    out = analysis.progress([], perf, notes)
    p5 = out["metrics"]["predicted_5k"]
    assert p5["verdict"] == "improving" and p5["to"]["value"] == "25:50"
    assert out["metrics"]["stations"]["sled_push"]["latest"]["weight_kg"] == 125
    assert any("wall_balls" in m for m in out["missing"])


def test_progress_with_provider_that_has_no_performance_metrics():
    out = analysis.progress([act("2026-10-01", vo2=48)], PerformanceMetrics(), [])
    assert "predicted_5k" not in out["metrics"]
    assert any("race predictions" in m for m in out["missing"])


def test_progress_endurance_threshold_and_impact():
    perf = PerformanceMetrics(
        endurance=EnduranceScore([("2026-08-01", 5154), ("2026-10-23", 5397)], 5414, {"running": 48, "hiit": 46}),
        hill_series=[("2026-08-01", 26), ("2026-10-29", 31)],
        lactate=LactateThreshold(167, 3.25, 378, "2026-10-28"),
        impact=[ImpactWeek("2026-10-12", 14790, 21383), ImpactWeek("2026-10-19", 16572, 21607)])
    m = analysis.progress([], perf, [])["metrics"]
    assert m["endurance_score"]["level_now"] == "intermediate" and m["endurance_score"]["contribution_pct"]["hiit"] == 46
    assert m["hill_score"]["verdict"] == "improving"
    assert m["lactate_threshold"]["pace"] == "5:08/km"
    assert m["running_impact_vs_tolerance"][-1]["pct_of_tolerance"] == 77


def test_aerobic_efficiency_skips_hard_and_short_runs():
    acts = [act("2026-10-01", hr=130), act("2026-10-02", hr=175), act("2026-10-03", hr=130, minutes=10),
            act("2026-10-04", "hiit", hr=130)]
    assert analysis.aerobic_efficiency(acts, max_hr=147) == [("2026-10-01", round(2.8 * 60 / 130, 3))]


def test_normalize_station_and_race_phase():
    assert analysis.normalize_station("Wall Balls") == "wall_balls"
    assert analysis.normalize_station("sled-push") == "sled_push"
    assert analysis.normalize_station("Box jumps") == "box_jumps"
    assert analysis.race_phase(date(2026, 11, 30), date(2026, 11, 25)) == "taper"
    phases = [{"phase": "PEAK", "from": "2026-11-09", "to": "2026-11-22"}]
    assert analysis.race_phase(date(2026, 11, 30), date(2026, 11, 10), phases) == "peak"
