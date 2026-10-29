# Hyrox Coach MCP

A local MCP server that turns **your own wearable data** into coaching for hybrid fitness races
(8 x 1 km runs, each followed by a functional station). Most coaching apps only understand running.
This one reads your recovery, your running plan and your training trends, and remembers the station
work your watch can't see.

> **Status:** early prototype (v0.2). Garmin is the only working data source today; others are planned
> (see [Data sources](#data-sources)). The Garmin source uses the **unofficial**
> [`garminconnect`](https://github.com/cyberjunky/python-garminconnect) library, which can break when
> Garmin changes its login, and may conflict with Garmin's terms of use. You use it with your own account
> at your own risk. Not affiliated with, endorsed by or sponsored by Garmin, Apple or HYROX; "HYROX" is a
> trademark of its respective owner and is used here only to describe the race format this tool helps you
> train for.
>
> **Not medical advice.** Stop and see a professional if you feel pain, illness or injury.

## What it does

| Tool | Answers |
|---|---|
| `get_readiness` | "Should I go hard today?" Readiness score, sleep, HRV, resting HR, last hard session, with a signal and reasons |
| `get_coach_plan` | Your wearable's running coach plan (Garmin Coach): phase, today's run and the week ahead with targets |
| `get_progress` | "Am I improving?" VO2 max, predicted 5k/10k/half, endurance score, hill score, lactate threshold, aerobic efficiency, running load vs tolerance, station progress |
| `get_training_summary` | Week-by-week runs, classes, load, load balance and acute:chronic ratio |
| `list_sessions` | Recent sessions and whether station notes were logged |
| `get_data_source` | Which wearable is connected and what it can supply |
| `log_session_note` | Saves what your watch can't see (sled weights, wall-ball sets, how it felt). Local only |
| `set_race_profile` / `get_race_profile` | Race date, division, goal, days to go, phase, station standards |

Everything is **read-only toward your wearable account**. Notes and your race profile live in a local
SQLite file (`~/.hyrox-coach/coach.db`). Responses are cached so agents don't hammer the provider.

## Data sources

Pick the one that matches your watch. Each source declares what it can supply, and the tools say "not
available" for the rest instead of failing. Station notes, the race profile and race planning work the same
for everyone.

| Source | Status | How it connects | Notes |
|---|---|---|---|
| **Garmin Connect** | ✅ Available | One-time login in your terminal; session tokens cached locally | Full feature set, including Garmin Coach plan and fitness trends |
| **Apple Health** (Apple Watch) | 🚧 Next | Import the Health app's *Export All Health Data* file (`export.xml`), parsed offline. Optional automatic sync with an iOS export app | Apple has no cloud API. No coach plan or readiness score, so those will be estimated and labelled as such. HRV is not comparable with Garmin's |
| **Oura** | 💡 Candidate | OAuth, personal use | Strongest on sleep, HRV and readiness. API terms to be checked first |
| **Polar** | 💡 Candidate | OAuth (AccessLink) | Workouts, sleep, recovery. API terms to be checked first |
| **Whoop** | 💡 Candidate | OAuth | Recovery, strain, sleep, workouts. API terms to be checked first |
| **Strava** | ⛔ Not supported | n/a | Strava's API policy prohibits feeding its data to AI tools and MCP servers. If you use Strava, add [Strava's official MCP](https://www.strava.com/legal/api_policy) next to this one |
| **Coros / Suunto** | ⛔ Not planned | n/a | Partner-only or unofficial APIs (not verified). Via Strava is not an option, see above |

What each source can supply today and in the plan:

| Capability | Garmin | Apple Health (planned) | Oura / Polar / Whoop (candidates) |
|---|---|---|---|
| Activities | ✅ | ✅ | Varies by provider |
| Sleep, HRV, resting HR | ✅ | ✅ | ✅ |
| Readiness score | ✅ Garmin's own | Estimated by this tool | Provider's own (Oura, Whoop) |
| Training load | ✅ | Estimated | Provider-specific |
| Running coach plan | ✅ Garmin Coach | ❌ | ❌ |
| Fitness trends (VO2 max, endurance score, race predictions) | ✅ | VO2 max only | Mostly ❌ |

Choose your source with `hyrox-coach login --provider garmin`, in `~/.hyrox-coach/config.toml`
(`provider = "garmin"`), or with the `HYROX_COACH_PROVIDER` environment variable. List what's available with
`hyrox-coach providers`. See the [design notes](docs/design/providers-and-install.md) for the architecture
and the research behind this list.

### How source-specific coaching works
The skill is **provider-neutral**: it holds the coaching method (routines, stations, training structure,
race strategy). Advice that depends on your watch, such as how to read its metrics, its traps and how to record
sessions on it, lives in a `GUIDE.md` for each source and is delivered by the `get_data_source` tool at the start of a
conversation. That way it works in any agent, not only ones that support skills, and one skill upload covers
every source. If a source has no running coach plan, the skill switches to planning the runs itself.

### Adding a data source
1. Create `src/hyrox_coach/providers/<name>/` with a provider that implements `Provider`
   ([base.py](src/hyrox_coach/providers/base.py)) and maps the source's data into the models in
   [models.py](src/hyrox_coach/models.py). Declare its `Capabilities` honestly.
2. Add a `GUIDE.md` with the required sections (see the [Garmin guide](src/hyrox_coach/providers/garmin/GUIDE.md)
   as a model). A test fails if a provider has no guide or is missing a section.
3. Register it in [providers/__init__.py](src/hyrox_coach/providers/__init__.py).
4. Add tests using small synthetic data, never real health data.

## Setup

Requires Python 3.12+.

```bash
git clone https://github.com/ebertoburgos/hyrox-coach-mcp.git && cd hyrox-coach-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Garmin
Log in once. You type your credentials in your own terminal; they are never stored, only the session
tokens Garmin returns (in `~/.garminconnect`, readable only by you):

```bash
.venv/bin/hyrox-coach login
```

Check what your watch and account provide:

```bash
.venv/bin/hyrox-coach doctor
```

If Garmin answers with `429` (rate limited), wait and try later. Don't retry logins in a loop.

### Apple Health
Not available yet. It will need no login: you export your data from the Health app and point the tool at the file.

### Upgrading from 0.1
The commands were renamed from `hybrid-coach` to `hyrox-coach`. The old names still work as aliases, so
existing MCP configs keep working, and your notes in `~/.hybrid-coach/` are copied to `~/.hyrox-coach/` on
first run. Python 3.12 is now required, so recreate your virtual environment with it.

## Connect it to an agent

### Claude Desktop
Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows), using the absolute path to your clone:

```json
{
  "mcpServers": {
    "hyrox-coach": {
      "command": "/absolute/path/to/hyrox-coach-mcp/.venv/bin/hyrox-coach-mcp"
    }
  }
}
```

Restart Claude Desktop (quit fully, then reopen). Then add the coaching playbook: zip `skills/hyrox-coach/`
and upload it in **Settings > Capabilities > Skills**, or paste its contents into a Project's instructions.

### Claude Code
```bash
claude mcp add hyrox-coach -- /absolute/path/to/hyrox-coach-mcp/.venv/bin/hyrox-coach-mcp
```
Copy `skills/hyrox-coach/` into `~/.claude/skills/`.

### Other local MCP clients (Cursor, OpenAI Agents SDK, …)
Run `.venv/bin/hyrox-coach-mcp` as a stdio server.

### ChatGPT
ChatGPT can only connect to hosted MCP servers, not local ones. A summary export you can upload to ChatGPT
is planned (see Roadmap).

## Getting better coaching out of it

- **Use your watch's running coach for your runs** (Garmin Coach) if it has one. This tool plans around it instead of competing with it.
- **After a class or simulation, tell the agent what you did**: "sled push 4x20 m at 125 kg, wall balls 3x20 unbroken, felt heavy". It saves this with the session. Station progress only exists if you log it.
- **Record simulations with a lap press at every run/station change.** Normal classes can stay one HIIT activity.

## Roadmap

**Data sources**
- Apple Health provider: `export.xml` import, plus optional automatic sync from an iOS export app
- Estimated readiness and training load for sources that don't provide them
- Oura, Polar and Whoop, after checking each provider's API terms

**Coaching tools**
- `analyze_session`: lap analysis for runs (pace fade, HR drift, coach-plan target compliance) and effort blocks inside HIIT classes
- `get_week_plan`: running plan plus classes on one calendar, with clash warnings
- `get_race_outlook` / `build_race_plan`: projected finish, weakest areas, per-run pacing, taper

**Install and sharing**
- `hyrox-coach setup` wizard (pick a source, connect it, check it)
- One-click Claude Desktop install (`.mcpb` bundle) and `uvx` install from PyPI
- Listing in the official MCP Registry
- `hyrox-coach export`: one markdown summary to upload to ChatGPT or any chat agent

## License

MIT, see [LICENSE](LICENSE).

## Privacy

Your data stays on your machine: provider session tokens (Garmin: `~/.garminconnect`), notes and cache in
`~/.hyrox-coach/`. The agent you connect will see the tool results, so the same privacy terms as that
agent apply. Health data is sensitive: never commit tokens, `data/` exports, health export files or `coach.db`.
