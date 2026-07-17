# garmin-coach

Personal cycling training assistant. A local, read-only Python MCP server that wraps
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect) so Claude can
analyze rides, recovery and training trends from Garmin Connect — combined with the
official Strava MCP for Strava-side data.

**Status: Milestone 5** — the local MCP server (`garmin-mcp`) exposes 17 read-only
tools plus a `plan_week` planning prompt: recent rides, per-activity
summaries/splits/zones/time-series, activity comparison, recovery context (training
status, readiness, HRV, sleep, resting HR, VO2 max, FTP), weekly training summaries,
and a one-call training-plan context bundle.

Strava integration (originally Milestone 4) was deliberately skipped: all Strava rides
originate from the same Garmin recordings, so it added dedup complexity without new
data. It can be added later via the official Strava MCP if segment/PR analysis becomes
interesting.

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
| `get_weekly_training_summary(weeks, end_date?)` | Per-ISO-week totals: rides, hours, distance, elevation, training load, hardest ride (≤12 weeks) |
| `get_training_plan_context(wellness_days)` | One-call bundle for planning: FTP, VO2 max, training status, last 14 days of rides, recent sleep/HRV/resting HR |

### Planning prompt

`/mcp__garmin__plan_week` (in Claude Code) starts a guided 7-day plan: Claude pulls the
context and weekly baseline, asks for anything Garmin can't know (subjective fatigue,
available days, indoor/outdoor), then produces a day-by-day plan where every session
has a purpose, duration, FTP-anchored intensity target, interval instructions, an
easier alternative for poor-recovery mornings, and a rationale. Plans are chat-only —
nothing is scheduled or uploaded to the device.

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

## Web app (dashboard + coach chat)

A local single-user web app: training dashboard (weekly volume/load, wellness trends,
ride detail with streams and zones, the Whistler plan), a fueling planner, plus a
Claude coach chat with live access to the Garmin tools.

The **weekly schedule** (`/schedule`) turns each plan week's sessions into a pool you
drag (or tap) onto whichever days fit your life — no fixed Tue/Thu/Sat/Sun. Assignments
persist in the browser; days show rides already recorded on Garmin; race day is locked
to Sep 12; "Review week with coach" sends your arrangement to the chat. The structured
sessions live in `training/whistler-sessions.json` (derived from the plan markdown).

The **fueling planner** (`/fuel`) builds a timed carbs/fluid/sodium schedule from ride
duration, intensity, sweat rate and product choices (Maurten, SiS, homemade mix, gels,
real food), with a Whistler preset, saved plans, print/PDF, and a "Review with coach"
handoff into the chat. Guidelines encoded: 30-60 g/h under 2 h, 60-90 g/h for 2-3 h,
90+ g/h beyond 3 h with dual-source (glucose+fructose) carbs; fluid anchored to sweat
rate; sodium to sweat concentration. It warns on >90 g/h without gut training,
over-drinking vs. sweat loss, and sodium shortfalls.

```bash
cd web && npm install && npm run build && cd ..   # build frontend once
garmin-coach-web                                   # serve everything on http://127.0.0.1:8787
```

Dev mode (hot reload): run `garmin-coach-web` in one terminal and `cd web && npm run dev`
in another, then open http://localhost:5173.

The chat is powered by the **Claude Agent SDK** using your local **Claude Code login** —
no API key needed. Prerequisites and caveats:

- Claude Code must be installed and logged in on this machine.
- Chat usage draws on your Claude subscription limits (model: Opus 4.8).
- The coach agent gets only the read-only `garmin-mcp` tools — no shell, file, or
  network tools — and other MCP servers on your machine are never loaded.
- The app binds to 127.0.0.1 and has no auth: never expose it to the internet.

## Use it from your phone (private, via Tailscale)

The app stays on this Mac — your phone reaches it over a private WireGuard network.
Garmin tokens never leave the machine and the chat keeps using your Claude
subscription. One-time setup:

1. **Install Tailscale on the Mac**: `brew install --cask tailscale-app`
   (asks for your macOS password), then open Tailscale.app and sign in.
2. **Install the Tailscale app on your phone** (App Store / Play Store), sign in with
   the same account.
3. **Expose the app to your tailnet with HTTPS** (server keeps its localhost binding):
   ```bash
   alias tailscale="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
   tailscale serve --bg http://127.0.0.1:8787
   tailscale serve status   # shows your https://<mac-name>.<tailnet>.ts.net URL
   ```
4. **On the phone**: open that URL → Share → **Add to Home Screen**. It installs as a
   standalone "Coach" app (PWA manifest + icons included).

The server auto-starts on login via launchd
(`deploy/com.garmin-coach.web.plist` → `~/Library/LaunchAgents/`, restarts on crash;
logs at `~/Library/Logs/garmin-coach.log`). The Mac must be awake to serve — enable
"Prevent automatic sleeping when the display is off" (System Settings → Displays →
Advanced, on power) or run `caffeinate`.

This setup is tailnet-only: nothing is exposed to the public internet, and devices on
your Tailscale account are the auth boundary.

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
