"""Garmin login and token handling.

Credentials are only ever typed interactively by the user in `hybrid-coach login`.
The MCP server never sees a password: it loads the cached tokens or fails with a
message telling the user to run the login command.
"""

import os
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin

TOKENSTORE = Path(os.getenv("GARMINTOKENS", "~/.garminconnect")).expanduser()


class NotLoggedIn(RuntimeError):
    pass


def client_from_tokens() -> Garmin:
    if not TOKENSTORE.exists():
        raise NotLoggedIn("No Garmin tokens found. Run `hybrid-coach login` in a terminal first.")
    api = Garmin()
    try:
        api.login(str(TOKENSTORE))
    except Exception as e:
        raise NotLoggedIn(
            f"Cached Garmin tokens did not work ({type(e).__name__}). "
            "Run `hybrid-coach login` in a terminal to refresh them."
        ) from e
    return api


def interactive_login() -> Garmin:
    # Reuse cached tokens if present; fall back to prompting for credentials.
    if TOKENSTORE.exists():
        try:
            return client_from_tokens()
        except NotLoggedIn as e:
            print(f"{e}\nLogging in again.")

    email = input("Garmin email: ").strip()
    password = getpass("Garmin password: ")
    api = Garmin(email, password, prompt_mfa=lambda: input("MFA code: ").strip())
    api.login(str(TOKENSTORE))
    TOKENSTORE.chmod(0o700)
    return api
