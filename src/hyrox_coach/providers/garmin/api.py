"""Cached, read-only access to the Garmin endpoints the coach uses.

Every call goes through the local cache so a conversation with an agent does not
hit Garmin repeatedly (Garmin rate-limits aggressively).
"""

import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectTooManyRequestsError

from ...store import Store
from .auth import client_from_tokens

MIN = 60
HOUR = 60 * MIN


class GarminData:
    def __init__(self, store: Store, client_factory: Callable[[], Garmin] = client_from_tokens):
        self.store = store
        self._factory = client_factory
        self._api: Garmin | None = None

    @property
    def api(self) -> Garmin:
        if self._api is None:
            self._api = self._factory()
        return self._api

    def _get(self, key: str, ttl_s: float, fetch: Callable[[Garmin], Any]) -> Any:
        hit = self.store.cached(key, ttl_s)
        if hit is not None:
            return hit
        try:
            value = fetch(self.api)
        except GarminConnectTooManyRequestsError:
            time.sleep(5)
            value = fetch(self.api)
        self.store.put(key, value)
        return value

    @staticmethod
    def _day_ttl(day: str) -> float:
        # Today's numbers keep changing; past days are settled.
        return 30 * MIN if day >= date.today().isoformat() else 24 * HOUR

    # --- daily recovery ---
    def training_readiness(self, day: str) -> list[dict]:
        return self._get(f"readiness:{day}", self._day_ttl(day), lambda a: a.get_training_readiness(day)) or []

    def sleep(self, day: str) -> dict:
        return self._get(f"sleep:{day}", self._day_ttl(day), lambda a: a.get_sleep_data(day)) or {}

    def hrv(self, day: str) -> dict:
        return self._get(f"hrv:{day}", self._day_ttl(day), lambda a: a.get_hrv_data(day)) or {}

    def user_summary(self, day: str) -> dict:
        return self._get(f"summary:{day}", self._day_ttl(day), lambda a: a.get_user_summary(day)) or {}

    # --- training ---
    def activities(self, start: str, end: str) -> list[dict]:
        return self._get(f"activities:{start}:{end}", 15 * MIN, lambda a: a.get_activities_by_date(start, end)) or []

    def training_status(self, day: str) -> dict:
        return self._get(f"training_status:{day}", 6 * HOUR, lambda a: a.get_training_status(day)) or {}

    def max_metrics(self, day: str) -> list | dict:
        return self._get(f"max_metrics:{day}", 6 * HOUR, lambda a: a.get_max_metrics(day)) or {}

    # --- Garmin Coach ---
    def coach_plan(self) -> dict | None:
        """The active Garmin Coach adaptive plan, or None if the user has none."""

        def fetch(a: Garmin) -> dict | None:
            plans = (a.get_training_plans() or {}).get("trainingPlanList", [])
            active = [p for p in plans if p.get("trainingPlanCategory") == "FBT_ADAPTIVE"
                      and p.get("trainingStatus", {}).get("statusKey") == "Scheduled"]
            if not active:
                return None
            return a.get_adaptive_training_plan_by_id(active[0]["trainingPlanId"])

        return self._get("coach_plan", 3 * HOUR, fetch)

    # --- trends ---
    def endurance_score(self, start: str, end: str) -> dict:
        return self._get(f"endurance:{start}:{end}", 6 * HOUR, lambda a: a.get_endurance_score(start, end)) or {}

    def hill_score(self, start: str, end: str) -> dict:
        return self._get(f"hill:{start}:{end}", 6 * HOUR, lambda a: a.get_hill_score(start, end)) or {}

    def race_predictions(self, start: str, end: str) -> list[dict]:
        return self._get(f"predictions:{start}:{end}", 6 * HOUR,
                         lambda a: a.get_race_predictions(start, end, "daily")) or []

    def running_tolerance(self, start: str, end: str) -> list[dict]:
        return self._get(f"tolerance:{start}:{end}", 6 * HOUR, lambda a: a.get_running_tolerance(start, end)) or []

    def lactate_threshold(self) -> dict:
        return self._get("lactate_threshold", 6 * HOUR, lambda a: a.get_lactate_threshold()) or {}


def days_ago(n: int, today: date | None = None) -> str:
    return ((today or date.today()) - timedelta(days=n)).isoformat()
