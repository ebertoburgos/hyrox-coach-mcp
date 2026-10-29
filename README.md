# Hyrox Coach MCP

A local MCP server that turns **your own Garmin data** into coaching for hybrid fitness races
(8 x 1 km runs, each followed by a functional station). Most coaching apps only understand running.
This one reads your recovery, your Garmin Coach running plan and your training trends, and remembers
the station work your watch can't see.

> **Status:** early prototype (v0.1). Built on the **unofficial** [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
> library, which can break when Garmin changes its login, and may conflict with Garmin's terms of use.
> You use it with your own account at your own risk. Not affiliated with, endorsed by or sponsored by Garmin or HYROX; "HYROX" is a trademark of its respective owner and is used here only to describe the race format this tool helps you train for.
>
> **Not medical advice.** Stop and see a professional if you feel pain, illness or injury.

## What it does

| Tool | Answers |
|---|---|
| `get_readiness` | "Should I go hard today?" Garmin readiness + sleep + HRV + resting HR + last hard session, with a signal and reasons |
| `get_coach_plan` | Your Garmin Coach plan: phase, today's run and the week ahead with targets |
| `get_progress` | "Am I improving?" VO2 max, predicted 5k/10k/half, endurance score, hill score, lactate threshold, aerobic efficiency, running load vs tolerance, station progress |
| `get_training_summary` | Week-by-week runs, classes, load, load balance and acute:chronic ratio |
| `list_sessions` | Recent sessions and whether station notes were logged |
| `log_session_note` | Saves what Garmin can't see (sled weights, wall-ball sets, how it felt). Local only |
| `set_race_profile` / `get_race_profile` | Race date, division, goal, days to go, phase, station standards |

Everything is **read-only toward Garmin**. Notes and your race profile live in a local SQLite file
(`~/.hybrid-coach/coach.db`). Responses are cached so agents don't hammer Garmin.

## Setup

Requires Python 3.11+.

```bash
git clone <this repo> hyrox-coach-mcp && cd hyrox-coach-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

Log in once. You type your credentials in your own terminal; they are never stored, only the session
tokens Garmin returns (in `~/.garminconnect`, readable only by you):

```bash
.venv/bin/hybrid-coach login
```

Check what your watch and account provide:

```bash
.venv/bin/hybrid-coach doctor
```

If Garmin answers with `429` (rate limited), wait and try later. Don't retry logins in a loop.

## Connect it to an agent

### Claude Desktop
Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows), using the absolute path to your clone:

```json
{
  "mcpServers": {
    "hybrid-coach": {
      "command": "/absolute/path/to/hyrox-coach-mcp/.venv/bin/hybrid-coach-mcp"
    }
  }
}
```

Restart Claude Desktop. Then add the coaching playbook: zip `skills/hybrid-coach/` and upload it in
**Settings > Capabilities > Skills**, or paste its contents into a Project's instructions.

### Claude Code
```bash
claude mcp add hybrid-coach -- /absolute/path/to/hyrox-coach-mcp/.venv/bin/hybrid-coach-mcp
```
Copy `skills/hybrid-coach/` into `~/.claude/skills/`.

### Other local MCP clients (Cursor, OpenAI Agents SDK, …)
Run `.venv/bin/hybrid-coach-mcp` as a stdio server.

### ChatGPT
ChatGPT can't launch local MCP servers. A summary export for ChatGPT is planned (see Roadmap).

## Getting better coaching out of it

- **Use Garmin Coach for your runs** if your watch supports it. The coach plans around it instead of competing with it.
- **After a class or simulation, tell the agent what you did**: "sled push 4x20 m at 125 kg, wall balls 3x20 unbroken, felt heavy". It saves this with the session. Station progress only exists if you log it.
- **Record simulations with a lap press at every run/station change.** Normal classes can stay one HIIT activity.

## Roadmap

- `analyze_session`: lap analysis for runs (pace fade, HR drift, Garmin Coach target compliance) and effort blocks inside HIIT classes
- `get_week_plan`: Garmin Coach runs plus classes on one calendar, with clash warnings
- `hybrid-coach export`: one markdown summary to upload to ChatGPT or any chat agent
- `get_race_outlook` / `build_race_plan`: projected finish, weakest areas, per-run pacing, taper

## License

MIT, see [LICENSE](LICENSE).

## Privacy

Your data stays on your machine: Garmin tokens in `~/.garminconnect`, notes and cache in
`~/.hybrid-coach/`. The agent you connect will see the tool results, so the same privacy terms as
that agent apply. Never commit tokens, `data/` exports or `coach.db`.
