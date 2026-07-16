# garmin-coach

Personal cycling training assistant. A local, read-only Python MCP server that wraps
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect) so Claude can
analyze rides, recovery and training trends from Garmin Connect — combined with the
official Strava MCP for Strava-side data.

**Status: Milestone 3** — the local MCP server (`garmin-mcp`) exposes 15 read-only
tools: recent rides, per-activity summaries/splits/zones/time-series, activity
comparison, and recovery context (training status, readiness, HRV, sleep, resting HR,
VO2 max, FTP). Garmin+Strava dedup arrives in Milestone 4.

## Requirements

- Python 3.12+ (developed on 3.14)
- A Garmin Connect account (MFA supported)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### One-time Garmin login

```bash
garmin-setup
```

Prompts for your Garmin email, password and (if enabled) MFA code. Credentials are used
once, in memory, to obtain OAuth tokens — they are never stored or logged. Tokens are
saved to `~/.garminconnect` (override with the `GARMINTOKENS` env var; see
`.env.example`). Sessions auto-refresh; if a session ever fully expires, commands will
tell you to re-run `garmin-setup`.

## Usage (Milestone 1)

```bash
garmin-coach recent-rides            # five most recent cycling activities
garmin-coach recent-rides --limit 10
garmin-coach recent-rides --json     # normalized JSON output
```

## Connect to Claude

The MCP server runs locally over stdio and is read-only.

**Claude Code** (from this project directory):

```bash
claude mcp add garmin -- /Users/anthonytrieu/Desktop/garmin/.venv/bin/garmin-mcp
```

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/Users/anthonytrieu/Desktop/garmin/.venv/bin/garmin-mcp"
    }
  }
}
```

### Available tools

| Tool | What it returns |
|---|---|
| `get_recent_activities(limit)` | Most recent cycling activities, normalized |
| `get_activity_summary(activity_id)` | Full single-ride summary incl. Garmin-reported IF/TSS/20-min power and FTP at ride time |
| `get_activity_splits(activity_id)` | Per-lap duration, distance, power, HR, cadence |
| `get_activity_power_data(activity_id)` | Time in power zones (boundaries from your Garmin settings) |
| `get_activity_heart_rate_data(activity_id)` | Time in HR zones |
| `get_activity_details(activity_id, max_points)` | Downsampled power/HR/cadence/speed/elevation streams |
| `compare_activities(a, b)` | Two summaries + locally calculated deltas |
| `get_training_status(date?)` | Status phrase, acute/chronic load, ACWR, monthly load balance vs. targets, VO2 max |
| `get_training_readiness(date?)` | Readiness score — reports honestly that Edge-only accounts don't have it |
| `get_recovery_time(date?)` | Recovery hours if exposed; explicit "unavailable" otherwise |
| `get_hrv_history(days, end_date?)` | Nightly HRV avg/high, weekly avg, status (≤14 days) |
| `get_sleep_history(days, end_date?)` | Sleep stages, score, overnight HRV, resting HR, body battery (≤14 days) |
| `get_resting_heart_rate_history(days, end_date?)` | Daily resting HR (≤14 days) |
| `get_vo2_max(date?)` | Cycling + generic VO2 max, fitness age |
| `get_current_ftp()` | FTP in watts, date set, staleness |

### Example questions

- "What are my five most recent rides?"
- "Break down yesterday's ride — how was my pacing across the laps?"
- "How much time did I spend in each power zone on my last ride?"
- "Compare my last two rides' average power and heart rate."
- "How has my sleep and HRV looked this week? Am I recovered enough for intervals?"
- "What's my current FTP and VO2 max?"

Claude calls `get_recent_activities(limit=N)` and receives normalized ride summaries:

```json
{
  "activity_id": 100000001,
  "name": "Morning Climb Repeats",
  "start_time_local": "2026-07-12T06:42:11",
  "distance_km": 46.28,
  "duration_s": 6488.0,
  "elevation_gain_m": 612.0,
  "avg_power_w": 186.0,
  "normalized_power_w": 204.0,
  "avg_hr_bpm": 148.0,
  "avg_cadence_rpm": 84.0,
  "source": "garmin",
  "power_note": "single-sided power meter (left-leg doubled); no L/R balance data"
}
```

If the Garmin session expires, the tool returns a clear error telling you to re-run
`garmin-setup`; rate limits (HTTP 429) return a wait-and-retry message.

## Development commands

```bash
.venv/bin/pytest        # tests (sanitized fixtures, no network)
.venv/bin/ruff check src tests   # lint
.venv/bin/ruff format src tests  # format
.venv/bin/mypy          # strict type checking
```

## Important limitations

- **Unofficial API**: python-garminconnect reverse-engineers the Garmin Connect web
  app. Garmin can change or block it at any time. All Garmin calls are isolated in
  `src/garmin_coach/client.py` so breakage is contained to one module.
- **Rate limits**: Garmin returns HTTP 429 under heavy use; commands fail fast with a
  clear message rather than retrying aggressively.
- **Single-sided power**: a Garmin Rally RS100 doubles left-leg power. Normalized data
  carries a `power_note` and no analysis will ever claim left/right balance.
- Read-only by design in v1: no activity edits, uploads, or workout scheduling.

## Project layout

```
src/garmin_coach/
  auth.py         token location + reauth messaging
  setup_login.py  `garmin-setup` interactive login (email/password/MFA)
  client.py       ONLY module touching garminconnect; maps errors
  models.py       normalized models (units, timestamps, source provenance)
  normalize.py    raw Garmin JSON -> models
  cli.py          `garmin-coach` verification CLI
tests/            unit tests with sanitized fixture data
docs/             architecture decision record
```

See [docs/architecture.md](docs/architecture.md) for design decisions and the milestone
roadmap.
