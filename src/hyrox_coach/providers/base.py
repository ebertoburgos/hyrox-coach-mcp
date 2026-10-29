"""The interface every wearable provider implements."""

from dataclasses import dataclass
from typing import Protocol

from ..models import (
    Activity, CoachPlan, HrvDay, LoadBalance, PerformanceMetrics, ProviderReadiness, SleepNight, Vitals,
)


@dataclass(frozen=True)
class Capabilities:
    """What a provider can supply. Tools use this to say 'not available' instead of failing."""

    activities: bool = True
    sleep: bool = False
    hrv: bool = False
    vitals: bool = False
    readiness: bool = False  # the provider computes its own readiness score
    load_balance: bool = False
    coach_plan: bool = False
    performance: bool = False  # predictions, endurance/hill score, threshold, impact vs tolerance


class ProviderUnavailable(RuntimeError):
    """Raised with a user-facing message when a provider is not connected or its data is missing."""


class Provider(Protocol):
    name: str
    label: str
    capabilities: Capabilities

    def activities(self, start: str, end: str) -> list[Activity]: ...
    def sleep(self, day: str) -> SleepNight | None: ...
    def hrv(self, day: str) -> HrvDay | None: ...
    def vitals(self, day: str) -> Vitals | None: ...
    def readiness(self, day: str) -> ProviderReadiness | None: ...
    def load_balance(self, day: str) -> LoadBalance | None: ...
    def coach_plan(self) -> CoachPlan | None: ...
    def performance(self, start: str, end: str) -> PerformanceMetrics: ...
    def check(self, day: str, start: str) -> list[tuple[str, str]]:
        """Connectivity/data check for `doctor`: [(label, 'ok' | 'empty ...' | 'FAILED ...')]."""
        ...
