"""MCP server: hybrid-race coaching tools over the athlete's own Garmin data."""

import functools
from datetime import date, datetime, timedelta
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import analysis
from .auth import NotLoggedIn
from .garmin import GarminData, days_ago
from .store import Store

INSTRUCTIONS = """\
Hybrid-race coach (8 x 1 km runs, each followed by a station: SkiErg, sled push, sled pull,
burpee broad jumps, row, farmers carry, sandbag lunges, wall balls).
Data comes from the athlete's own Garmin account, read-only. Garmin cannot see what happens
inside HIIT/class sessions, so ask the athlete for station details after those sessions and
store them with log_session_note. Each tool lists what data is missing; ask for it rather than guessing.
Not medical advice: if the athlete reports pain, illness or injury, tell them to stop and see a professional.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

mcp = MCPServer("hybrid-coach", instructions=INSTRUCTIONS)
store = Store()
garmin = GarminData(store)


def _guard(fn):
    """Turn auth problems into a clear instruction instead of a stack trace."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotLoggedIn as e:
            return {"error": str(e)}

    return wrapper


def _race_context(today: date) -> dict[str, Any] | None:
    profile = store.profile()
    race = profile.get("race_date")
    if not race:
        plan = garmin.coach_plan()
        summary = analysis.coach_plan(plan, today, 0, [])
        race = summary.get("event_date")
        if not race:
            return None
        profile = {**profile, "race_date": race, "race_date_source": "Garmin Coach plan end (unconfirmed)"}
    days = (date.fromisoformat(race) - today).days
    return {**profile, "days_to_race": days}


@mcp.tool(annotations=READ_ONLY)
@_guard
def get_readiness(day: str | None = None) -> dict[str, Any]:
    """Recovery and readiness for a day (default today): Garmin readiness and its limiting
    factors, sleep, HRV vs baseline, resting HR, Body Battery, last hard session, and a
    signal (ready_for_hard / easy / rest_or_very_easy) with reasons. Pair it with
    get_coach_plan to decide today's session."""
    d = day or date.today().isoformat()
    now = datetime.now() if d == date.today().isoformat() else datetime.fromisoformat(d + "T23:59:00")
    acts = garmin.activities(days_ago(7, now.date()), d)
    out = analysis.readiness(garmin.training_readiness(d), garmin.sleep(d), garmin.hrv(d),
                             garmin.user_summary(d), acts, now)
    out["race"] = _race_context(now.date())
    return out


@mcp.tool(annotations=READ_ONLY)
@_guard
def get_coach_plan(days_ahead: int = 7) -> dict[str, Any]:
    """The athlete's Garmin Coach running plan: phase (build/peak/taper), week number, event
    date, today's workout and upcoming workouts with targets (HR or pace), and run consistency
    since the plan started. Garmin Coach owns the runs; plan stations and classes around them."""
    today = date.today()
    plan = garmin.coach_plan()
    since = plan["startDate"][:10] if plan else days_ago(28)
    return analysis.coach_plan(plan, today, days_ahead, garmin.activities(since, today.isoformat()))


@mcp.tool(annotations=READ_ONLY)
@_guard
def get_progress(weeks: int = 12) -> dict[str, Any]:
    """How the athlete is improving over the last N weeks, Garmin Coach style: VO2 max,
    predicted 5k/10k/half, endurance score (and HIIT vs running contribution), hill score,
    lactate threshold, aerobic efficiency on easy runs, running impact vs tolerance, plus
    station progress from logged notes. Each metric has a verdict (improving/stable/declining)."""
    today = date.today().isoformat()
    start = days_ago(weeks * 7)
    return analysis.progress(
        garmin.activities(start, today), garmin.race_predictions(start, today),
        garmin.endurance_score(start, today), garmin.hill_score(start, today),
        garmin.lactate_threshold(), garmin.running_tolerance(start, today), store.notes(start),
    )


@mcp.tool(annotations=READ_ONLY)
@_guard
def get_training_summary(weeks: int = 4) -> dict[str, Any]:
    """Week-by-week training: run km and count, hybrid/class sessions, hours, training load,
    hard sessions, plus Garmin's 4-week load balance (aerobic low/high, anaerobic vs targets)
    and acute:chronic load ratio."""
    today = date.today()
    start = (today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)).isoformat()
    return analysis.training_summary(garmin.activities(start, today.isoformat()), weeks, today,
                                     garmin.training_status(today.isoformat()))


@mcp.tool(annotations=READ_ONLY)
@_guard
def list_sessions(days: int = 14, kind: str | None = None) -> list[dict[str, Any]]:
    """Recent sessions, newest first. kind filters to 'run', 'hybrid' (HIIT/classes/strength)
    or 'other'. has_note shows whether station details were logged."""
    start = days_ago(days)
    acts = garmin.activities(start, date.today().isoformat())
    if kind:
        acts = [a for a in acts if analysis.kind(a) == kind]
    notes = store.notes(start)
    return analysis.session_rows(acts, {n["activity_id"] for n in notes if n["activity_id"]},
                                 {n["date"] for n in notes})


class StationEntry(BaseModel):
    station: str = Field(description="skierg, sled_push, sled_pull, burpee_broad_jumps, row, "
                                     "farmers_carry, sandbag_lunges, wall_balls, or another exercise name")
    weight_kg: float | None = None
    reps: int | None = None
    sets: int | None = None
    distance_m: float | None = None
    time_s: float | None = Field(None, description="Time for the effort, in seconds")
    unbroken: bool | None = None
    rpe: int | None = Field(None, description="Effort 1-10")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
@_guard
def log_session_note(text: str, day: str | None = None, activity_id: int | None = None,
                     stations: list[StationEntry] | None = None) -> dict[str, Any]:
    """Save what the athlete did in a session that Garmin cannot see (stations, weights, reps,
    times, how it felt). Stored locally only, never sent to Garmin. Extract structured stations
    from what the athlete says; keep their own words in text. Defaults to today."""
    d = day or date.today().isoformat()
    if activity_id is None:
        same_day = [a for a in garmin.activities(d, d) if analysis.kind(a) == "hybrid"]
        if len(same_day) == 1:
            activity_id = same_day[0]["activityId"]
    entries = [{**s.model_dump(), "station": analysis.normalize_station(s.station)} for s in stations or []]
    note_id = store.add_note(d, text, entries, activity_id)
    return {"saved": note_id, "date": d, "activity_id": activity_id, "stations": entries}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
@_guard
def set_race_profile(race_date: str | None = None, division: str | None = None,
                     location: str | None = None, goal: str | None = None) -> dict[str, Any]:
    """Set the athlete's race details (stored locally). division: open_men, open_women,
    pro_men, pro_women, doubles_men, doubles_women, doubles_mixed. goal is free text,
    e.g. 'finish strong' or 'sub 1:30'. Only the fields given are changed."""
    store.set_profile(race_date=race_date, division=division, location=location, goal=goal)
    return get_race_profile()


@mcp.tool(annotations=READ_ONLY)
@_guard
def get_race_profile() -> dict[str, Any]:
    """Race date, days to go, current phase (build/peak/taper/race day), division and goal,
    plus the race format and station standards for the division."""
    today = date.today()
    ctx = _race_context(today)
    if not ctx:
        return {"missing": ["race date: ask the athlete and call set_race_profile"]}
    plan = analysis.coach_plan(garmin.coach_plan(), today, 0, [])
    ctx["phase"] = analysis.race_phase(date.fromisoformat(ctx["race_date"]), today, plan.get("phases"))
    division = ctx.get("division", "")
    weights_key = division.replace("doubles_mixed", "open_men").replace("doubles_", "open_")
    ctx["format"] = {"runs": "8 x 1 km", "stations": analysis.RACE_FORMAT["stations"],
                     "weights": analysis.RACE_FORMAT["divisions"].get(weights_key),
                     "note": "Check weights against your event's current rulebook."}
    if not division:
        ctx["missing"] = ["division: ask the athlete (open/pro/doubles, men/women)"]
    return ctx


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
