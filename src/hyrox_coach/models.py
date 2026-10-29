"""Provider-independent data model.

Every provider (Garmin, Apple Health, ...) maps its own data into these classes.
`analysis.py` consumes only these, never a provider's raw JSON. Anything a provider
cannot supply is None or empty, and the tools report it as missing.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

RUN_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "indoor_running", "virtual_run"}
HYBRID_TYPES = {"hiit", "strength_training", "indoor_cardio", "cardio", "obstacle_run", "obstacle_racing"}


def kind_for(sport_key: str) -> str:
    if sport_key in RUN_TYPES:
        return "run"
    if sport_key in HYBRID_TYPES:
        return "hybrid"
    return "other"


@dataclass
class Activity:
    id: int
    start: datetime  # local time
    name: str | None
    sport_key: str
    duration_s: float = 0.0
    distance_m: float = 0.0
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_speed_mps: float | None = None
    load: float | None = None  # provider training load, if it has one
    anaerobic_te: float | None = None
    vo2max: float | None = None

    @property
    def day(self) -> str:
        return self.start.date().isoformat()

    @property
    def kind(self) -> str:
        return kind_for(self.sport_key)


@dataclass
class SleepNight:
    day: str
    total_s: float
    deep_s: float = 0.0
    rem_s: float = 0.0
    score: int | None = None


@dataclass
class HrvDay:
    day: str
    last_night: float | None
    weekly_avg: float | None
    baseline_low: float | None = None
    baseline_high: float | None = None
    status: str | None = None
    # How the value is computed. Values are only comparable within the same method.
    method: str = "unknown"  # "rmssd" | "sdnn" | "unknown"


@dataclass
class Vitals:
    day: str
    resting_hr: float | None = None
    resting_hr_7d: float | None = None
    body_battery_now: int | None = None
    body_battery_peak: int | None = None


@dataclass
class ProviderReadiness:
    """A readiness score computed by the provider itself (Garmin has one, Apple does not)."""

    score: int | None
    level: str | None
    feedback: str | None
    factor_ratings: dict[str, str] = field(default_factory=dict)  # human label -> POOR/MODERATE/GOOD
    recovery_hours: float | None = None
    acute_load: float | None = None
    source: str = "provider"


@dataclass
class PlannedWorkout:
    day: str
    name: str | None = None
    target: str | None = None
    est_minutes: int = 0
    est_km: float = 0.0
    key_workout: bool = False
    status: str | None = None
    rest: bool = False


@dataclass
class PlanPhase:
    phase: str
    start: str
    end: str
    current: bool = False


@dataclass
class CoachPlan:
    name: str | None
    level: str | None
    start: date
    duration_weeks: int | None
    avg_weekly_workouts: int
    phases: list[PlanPhase]
    workouts: list[PlannedWorkout]

    @property
    def event_date(self) -> str | None:
        return next((p.start for p in self.phases if p.phase == "TARGET_EVENT_DAY"), None)

    @property
    def current_phase(self) -> str | None:
        return next((p.phase for p in self.phases if p.current), None)


@dataclass
class LoadBalance:
    """Four-week training load by intensity bucket, as [actual, target_min, target_max]."""

    feedback: str | None
    aerobic_low: list[float | None]
    aerobic_high: list[float | None]
    anaerobic: list[float | None]
    status: str | None = None
    acute_chronic_ratio: float | None = None
    acwr_status: str | None = None


@dataclass
class Prediction:
    day: str
    t5k: float | None = None
    t10k: float | None = None
    half: float | None = None


@dataclass
class EnduranceScore:
    series: list[tuple[str, float]]
    current: float | None
    contributions: dict[str, int] = field(default_factory=dict)  # label -> percent


@dataclass
class LactateThreshold:
    hr: int
    speed_mps: float | None
    ftp_w: float | None
    as_of: str


@dataclass
class ImpactWeek:
    week_of: str
    impact_load: float
    tolerance: float


@dataclass
class PerformanceMetrics:
    """Provider-computed fitness trends. Most are Garmin-specific; others leave them empty."""

    predictions: list[Prediction] = field(default_factory=list)
    endurance: EnduranceScore | None = None
    hill_series: list[tuple[str, float]] = field(default_factory=list)
    lactate: LactateThreshold | None = None
    impact: list[ImpactWeek] = field(default_factory=list)
