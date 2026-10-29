"""Command line: `hyrox-coach login` and `hyrox-coach doctor`."""

import argparse
import dataclasses
import sys
import time
from datetime import date, timedelta

from . import config
from .providers import AVAILABLE, PLANNED, ProviderUnavailable, get_provider
from .store import Store


def login(args: argparse.Namespace) -> int:
    name = args.provider or config.provider_name()
    if name == "garmin":
        from .providers.garmin import auth as garmin_auth

        t0 = time.time()
        api = garmin_auth.interactive_login()
        print(f"Logged in as {api.get_full_name()} in {time.time() - t0:.1f}s. Tokens cached in {garmin_auth.TOKENSTORE}")
    else:
        print(f"Provider '{name}' needs no login or is not available yet. Available: {', '.join(AVAILABLE)}")
        return 1
    config.save_provider(name)
    print(f"Provider set to '{name}'.")
    return 0


def doctor(args: argparse.Namespace) -> int:
    """Check the provider connection and which data it supplies. Never prompts for credentials."""
    name = args.provider or config.provider_name()
    try:
        p = get_provider(name, Store())
    except ProviderUnavailable as e:
        print(e)
        return 1
    print(f"Provider: {p.label} ({name})")
    print(f"Capabilities: {', '.join(k for k, v in dataclasses.asdict(p.capabilities).items() if v)}\n")
    today = date.today()
    t0 = time.time()
    try:
        results = p.check(today.isoformat(), (today - timedelta(days=28)).isoformat())
    except ProviderUnavailable as e:
        print(e)
        return 1
    print(f"Checked in {time.time() - t0:.1f}s\n")
    failed = 0
    for label, status in results:
        failed += status.startswith("FAILED")
        print(f"  {label:<20} {status}")
    return 1 if failed else 0


def providers(_: argparse.Namespace) -> int:
    current = config.provider_name()
    for name, desc in AVAILABLE.items():
        print(f"{'*' if name == current else ' '} {name:<14} {desc}")
    for name, desc in PLANNED.items():
        print(f"  {name:<14} {desc}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="hyrox-coach")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("login", help="Connect your wearable account once and cache the session")
    p.add_argument("--provider", help="e.g. garmin (default: configured provider)")
    p.set_defaults(fn=login)
    p = sub.add_parser("doctor", help="Check the connection and which metrics are available")
    p.add_argument("--provider")
    p.set_defaults(fn=doctor)
    sub.add_parser("providers", help="List available and planned data sources").set_defaults(fn=providers)
    args = parser.parse_args()
    sys.exit(args.fn(args))
