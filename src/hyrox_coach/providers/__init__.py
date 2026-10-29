"""Provider registry. Add a provider here and it becomes selectable in config and the CLI.

Each provider is a package `providers/<name>/` holding its code and a GUIDE.md: the coaching notes the
agent receives from `get_data_source` (what the source supplies, how to read its metrics, its traps).
"""

from collections.abc import Callable
from importlib.resources import files

from ..store import Store
from .base import Capabilities, Provider, ProviderUnavailable

AVAILABLE = {
    "garmin": "Garmin Connect (unofficial login, full feature set including Garmin Coach)",
}
PLANNED = {
    "apple_health": "Apple Health export (coming soon)",
}


def _garmin(store: Store) -> Provider:
    from .garmin import GarminProvider

    return GarminProvider(store)


FACTORIES: dict[str, Callable[[Store], Provider]] = {"garmin": _garmin}


def get_provider(name: str, store: Store) -> Provider:
    try:
        return FACTORIES[name](store)
    except KeyError:
        known = ", ".join(AVAILABLE)
        hint = f" ({PLANNED[name]})" if name in PLANNED else ""
        raise ProviderUnavailable(f"Provider '{name}' is not available{hint}. Available now: {known}.") from None


def guide(name: str) -> str:
    """Coaching notes for a provider, read from its GUIDE.md."""
    return (files(__package__) / name / "GUIDE.md").read_text(encoding="utf-8")


__all__ = ["guide", "AVAILABLE", "PLANNED", "Capabilities", "Provider", "ProviderUnavailable", "get_provider"]
