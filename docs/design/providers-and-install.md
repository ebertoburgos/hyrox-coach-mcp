# Design: multiple wearable providers and easy install

Status: proposal (2026-10-29). Research sources are linked inline. Check the legal readings against the primary sources; this is not legal advice.

## Goals
1. Let a user choose where their data comes from: Garmin today, then Apple Health and others.
2. Make installation possible for non-developers, without a terminal where possible.
3. Keep the coaching layer (analysis, tools, skill) independent of any one provider.

## Research findings that shape this design

| Finding | Impact |
|---|---|
| **Strava's API Policy (effective 2026-06-01) prohibits MCP servers and AI context-window use of Strava data** (§5.3, §5.16(b)). The official Strava MCP is the only authorized agent interface (§3.5). [policy](https://www.strava.com/legal/api_policy) | **No Strava provider.** The README tells Strava users to add the official Strava MCP alongside this one. |
| **`garminconnect` is now 0.3.20 and requires Python ≥ 3.12.** Releases are frequent because Garmin keeps changing its login. `garth` is deprecated. [repo](https://github.com/cyberjunky/python-garminconnect) | Move to Python 3.12+ and `garminconnect~=0.3.20`. Keep the Garmin code isolated so breakage stays contained. |
| **Apple has no cloud API.** Data is available through the Health app's `export.xml` or an iOS automation app. | Apple is a **file-based provider**, with no login. |
| `healthkit-to-sqlite` is stale (2021). [`apple-health-parser`](https://github.com/alxdrcirilo/apple-health-parser) 2.0.5 is maintained. Since iOS 16, workout totals sit in `WorkoutStatistics`, which breaks older parsers. | Use our own streaming `iterparse` over only the record types we need, with `apple-health-parser` as a reference. Exports can be several GB. |
| [Health Auto Export](https://www.healthyapps.dev/) (iOS, ~$25 lifetime) can export JSON automatically to iCloud Drive or Dropbox on a schedule. | Optional "auto-sync" mode for Apple: watch a folder of JSON files instead of re-exporting by hand. |
| Oura v2, Polar AccessLink and Whoop v2 all offer OAuth that individuals can register. Their AI-use terms are **not yet checked**. | Later providers. Check each provider's terms before building, given what Strava did. |
| **MCP Bundles (`.mcpb`) support `"server.type": "uv"`**: ship `pyproject.toml`, and Claude Desktop installs the dependencies with uv. Python isn't needed on the user's machine. `user_config` supports file and directory pickers, plus `sensitive` fields stored in the OS keychain. [spec](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md) | One-click Claude Desktop install is realistic. |
| The MCP spec **forbids requesting passwords via form elicitation**. URL-mode elicitation is intended for third-party sign-in. [spec](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation) | Garmin sign-in happens on a **local browser page** the server opens, never in the chat. |
| ChatGPT supports only **remote** MCP servers. Local stdio needs OpenAI's org-bound tunnel. | ChatGPT stays on the `AGENTS.md` + `export` path. The OpenAI Agents SDK can use stdio (`MCPServerStdio`). |
| [open-wearables](https://github.com/the-momentum/open-wearables) (2.7k★, MIT) normalizes ~11 providers into daily summaries, events and time series. | Borrow its data-model shape. Don't depend on it: it's a hosted FastAPI stack, too heavy for "install and go". |

## Provider architecture

```
src/hyrox_coach/
  models.py          # normalized dataclasses (below)
  providers/
    base.py          # Provider protocol + Capabilities
    garmin.py        # current garmin.py, mapped to models
    apple_health.py  # export.xml / Health Auto Export JSON -> local SQLite -> models
    __init__.py      # registry: {"garmin": GarminProvider, "apple_health": AppleHealthProvider}
  readiness.py       # our own readiness estimate when a provider has none
  analysis.py        # consumes models only, never raw provider JSON
  server.py          # tools check capabilities and report "missing" / "not available"
  config.py          # ~/.hyrox-coach/config.toml: provider + provider settings
  connect/           # local browser sign-in page (Garmin now; OAuth providers later)
  cli.py             # setup, connect, import, doctor, export
```

### Normalized models (shape borrowed from open-wearables)
- `Activity`: id, start, sport (`run` / `hybrid` / `other`), duration, distance, avg/max HR, load (optional), source.
- `Lap`: index, duration, distance, avg HR, avg speed. Optional; Apple workout segments map here.
- `SleepNight`: date, total, deep, REM, score (optional).
- `HrvDay`: date, value, **method** (`rmssd` for Garmin, `sdnn` for Apple), baseline range (optional). Values are compared only within the same method.
- `RestingHr`, `Vo2Max`: date and value.
- `ProviderReadiness`: score, level, factors. Optional (Garmin only).
- `CoachPlan` / `PlannedWorkout`: optional (Garmin Coach only).
- `Trend`: name, points. For provider-specific metrics such as endurance score, hill score and race predictions.

### Capabilities
Each provider declares what it supplies. Tools adapt to that instead of failing:

| Capability | Garmin | Apple Health |
|---|---|---|
| Activities, laps | ✅ | ✅ (laps from workout segments when recorded) |
| Sleep, HRV, resting HR, VO2 max | ✅ | ✅ |
| Provider readiness | ✅ | ❌, so we use `readiness.py` (HRV/RHR vs personal baseline, sleep, recent load), labelled "estimated" |
| Training load | ✅ | ❌, so we estimate it from duration × HR zones (TRIMP) |
| Coach plan | ✅ Garmin Coach | ❌, so `get_coach_plan` returns "not available for Apple Health" |
| Endurance/hill score, race predictions | ✅ | ❌ |
| Freshness | Live (cached API) | As fresh as the last export or auto-sync |

Station notes, race profile, race outlook and race plan are provider-independent and work the same for everyone.

## Install experience

### Tier 1: Claude Desktop, no terminal (`.mcpb`)
1. Download `hyrox-coach.mcpb` from GitHub Releases and double-click it.
2. Claude Desktop shows the setup form (`user_config`):
   - **Data source**: text field, `garmin` or `apple_health`. MCPB has no dropdown type, so the tool also validates it.
   - **Apple Health export**: file picker (`export.zip`/`export.xml`), or a folder picker for Health Auto Export.
3. First chat: the agent calls `connect_provider`.
   - **Garmin:** the server opens `http://127.0.0.1:<port>/connect` in the browser. The user signs in on that local page, including MFA. Tokens are saved to the user's keychain or a 0600 file. The password never passes through the chat or the agent.
   - **Apple Health:** imports the selected file into local SQLite and reports what it found.
4. The skill ships as a separate zip in the same release, uploaded in Settings → Skills.

### Tier 2: Developers and other clients (PyPI + `uvx`)
```json
{ "mcpServers": { "hyrox-coach": { "command": "uvx", "args": ["hyrox-coach-mcp"] } } }
```
- `uvx hyrox-coach-mcp setup` is an interactive wizard:
  1. Pick a provider.
  2. Connect it (browser sign-in or a file path).
  3. Run `doctor`.
  4. Offer to write the Claude Desktop and Claude Code configs, showing the change first.
- Works for Claude Code, Cursor and the OpenAI Agents SDK (`MCPServerStdio`).

### Tier 3: Discoverability
- Publish to the official MCP Registry (`server.json`, `mcp-name: io.github.ebertoburgos/hyrox-coach-mcp`).

### ChatGPT
- `hyrox-coach export --days 28` writes a markdown summary, uploaded together with `AGENTS.md`. There is no hosted server, by design.

## Rename at the same time
The refactor touches every module, and the `.mcpb`/`uvx` install replaces today's manual config. That makes it the cheapest moment to align names with the project:
- Module `hybrid_coach` → `hyrox_coach`.
- Commands `hybrid-coach` / `hybrid-coach-mcp` → `hyrox-coach` / `hyrox-coach-mcp`.
- Data folder `~/.hybrid-coach` → `~/.hyrox-coach`, migrated automatically on first run.
- The existing Claude Desktop entry is updated once, after confirmation.

## Delivery order
1. **Foundation**
   - Python 3.12, `garminconnect~=0.3.20`.
   - Models, provider protocol, capabilities and config, with Garmin moved behind them.
   - Rename.
   - Behaviour for Garmin users stays the same; existing tests are ported to models.
2. **Apple Health provider**
   - Streaming `export.xml` import (tested on a synthetic export).
   - Health Auto Export folder mode.
   - `readiness.py` estimator and TRIMP load.
3. **Install**
   - `connect_provider` with local browser sign-in, `setup` wizard and `doctor` per provider.
   - `.mcpb` (`server.type: uv`), PyPI release, MCP Registry listing.
4. **Later**
   - Oura / Polar / Whoop, after checking their terms.
   - `export` for ChatGPT.

## Open questions
- **Apple parser:** should we write our own minimal `iterparse` (fewer dependencies; we only need about 8 record types) or depend on `apple-health-parser`? Recommendation: our own, with that library as a reference.
- **Releases:** who signs and publishes them (PyPI account, GitHub Releases)? Publishing is outward-facing and needs the maintainer's go-ahead.
- **Trademark:** "Hyrox" appears in the package and registry names. Confirm with IP Legal before publishing to PyPI or the MCP Registry.

---
Created using Anthropic Claude. Keep this on internal versions until a human has reviewed and verified the content, especially the legal readings of the Strava policy.
