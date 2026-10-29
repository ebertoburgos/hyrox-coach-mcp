"""Command line: `hybrid-coach login` and `hybrid-coach doctor`."""

import argparse
import sys
import time
from datetime import date

from . import auth
from .auth import NotLoggedIn
from .garmin import GarminData, days_ago
from .store import Store


def login(_: argparse.Namespace) -> int:
    t0 = time.time()
    api = auth.interactive_login()
    print(f"Logged in as {api.get_full_name()} in {time.time() - t0:.1f}s. Tokens cached in {auth.TOKENSTORE}")
    return 0


def doctor(_: argparse.Namespace) -> int:
    """Check tokens work and which data your watch/account provides. Never prompts for credentials."""
    data = GarminData(Store())
    try:
        t0 = time.time()
        name = data.api.get_full_name()
    except NotLoggedIn as e:
        print(e)
        return 1
    print(f"Logged in from cached tokens as {name} ({time.time() - t0:.1f}s)\n")

    today = date.today().isoformat()
    start = days_ago(28)
    checks = {
        "training readiness": lambda: data.training_readiness(today),
        "sleep": lambda: data.sleep(today),
        "hrv": lambda: data.hrv(today),
        "daily summary": lambda: data.user_summary(today),
        "activities (28d)": lambda: data.activities(start, today),
        "training status": lambda: data.training_status(today),
        "garmin coach plan": lambda: data.coach_plan(),
        "endurance score": lambda: data.endurance_score(start, today),
        "hill score": lambda: data.hill_score(start, today),
        "race predictions": lambda: data.race_predictions(start, today),
        "running tolerance": lambda: data.running_tolerance(start, today),
        "lactate threshold": lambda: data.lactate_threshold(),
    }
    failed = 0
    for label, fn in checks.items():
        try:
            status = "ok" if fn() else "empty (not supported by your watch or no data yet)"
        except Exception as e:
            failed += 1
            status = f"FAILED {type(e).__name__}: {str(e)[:80]}"
        print(f"  {label:<20} {status}")
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="hybrid-coach")
    sub = parser.add_subparsers(required=True)
    sub.add_parser("login", help="Log in to Garmin Connect once and cache tokens").set_defaults(fn=login)
    sub.add_parser("doctor", help="Check your tokens and which metrics are available").set_defaults(fn=doctor)
    args = parser.parse_args()
    sys.exit(args.fn(args))
