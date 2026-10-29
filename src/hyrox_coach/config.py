"""User configuration: which provider to use. Stored at ~/.hyrox-coach/config.toml."""

import os
import tomllib

from .store import HOME

CONFIG_PATH = HOME / "config.toml"
DEFAULT_PROVIDER = "garmin"


def load() -> dict:
    try:
        return tomllib.loads(CONFIG_PATH.read_text())
    except FileNotFoundError:
        return {}


def provider_name() -> str:
    """Env var wins, then config.toml, then Garmin (the only provider shipped so far)."""
    return os.getenv("HYROX_COACH_PROVIDER") or load().get("provider") or DEFAULT_PROVIDER


def save_provider(name: str) -> None:
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    CONFIG_PATH.write_text(f'provider = "{name}"\n')
