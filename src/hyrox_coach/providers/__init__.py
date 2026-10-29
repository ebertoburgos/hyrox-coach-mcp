"""Provider registry. Add a provider here and it becomes selectable in config and the CLI."""

from collections.abc import Callable

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


__all__ = ["AVAILABLE", "PLANNED", "Capabilities", "Provider", "ProviderUnavailable", "get_provider"]
