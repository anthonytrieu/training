# Build log — how this project was made

A chronological record of everything built in this project, why each decision was
made, and how each piece was verified. All of it was built on **July 16, 2026** in a
series of working sessions with Claude (Claude Code), starting from an empty folder.

---

## The idea

A personal cycling training assistant for one rider (Garmin Edge 540, Rally RS100
single-sided power meter, training for the RBC GranFondo Whistler on Sep 12, 2026).
Requirements set at the start:

- Claude as the conversation/reasoning layer, Garmin data via a local MCP server
- Credentials and tokens stay on this machine; tools read-only in v1
- Honest coaching: recorded facts vs. calculated values vs. interpretation,
  no invented zones, no left/right power claims (single-sided meter), no medical advice
- Build incrementally in milestones

## Milestone 1 — Garmin authentication + first data

**What:** Python package `garmin_coach` wrapping
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect) (an
*unofficial*, reverse-engineered Garmin Connect client — it can break any time).

**How:**
- The library source was cloned and inspected first so every method name used
  actually exists — nothing guessed.
- `setup_login.py` → `garmin-setup`: interactive email/password/MFA login. Credentials
  live only in process memory; OAuth tokens persist to `~/.garminconnect` (outside the
  repo) and auto-refresh.
- `client.py`: the **only** module that touches the library, so breakage from Garmin
  changes is contained to one file. Library exceptions map to typed errors with
  actionable messages ("run `garmin-setup`", "rate limited — wait").
- `normalize.py` + `models.py`: raw Garmin JSON → stable models with units in field
  names (`distance_km`, `avg_power_w`), ISO-8601 timestamps, `source: "garmin"`
  provenance, `None` for missing data, and an automatic single-sided-power note on any
  ride with power.
- Verified with `garmin-coach recent-rides` printing 5 real rides.

## Milestone 2 — MCP server

**What:** `garmin-mcp`, a FastMCP (official `mcp` SDK) stdio server exposing one tool,
`get_recent_activities`, registered with Claude Code via `claude mcp add`.

**How / key decisions:**
- Login is **lazy and cached**: the server starts instantly even if the Garmin session
  is dead; auth failures surface as tool errors, and the cached client drops so a
  re-run of `garmin-setup` fixes it without restarting the server.
- stdio discipline: stdout carries only MCP protocol; all logging to stderr.
- Verified three ways: in-memory MCP protocol tests, a live stdio client script, and
  finally Claude itself calling the tool.

## Milestone 3 — full ride analysis + recovery tools (15 tools)

**How:** before writing any normalizer, one capture script hit all 13 endpoints
against the live account and saved the raw responses; normalizers were designed
against real shapes, then the captures were sanitized (fake IDs, GPS nulled) and
committed as test fixtures.

**Honest-data findings from the captures:**
- Garmin records IF/TSS/FTP-at-ride-time itself → exposed as *Garmin-reported*, never
  recomputed locally.
- Training readiness and recovery time are **watch features** — an Edge-only account
  has neither. Those tools return `available: false` with the reason instead of
  estimating.

Tools added: activity summary/splits/power zones/HR zones/time-series (downsampled),
compare_activities, training status (ACWR, load balance), HRV/sleep/resting-HR
histories (per-day loops, capped at 14 days for rate-limit respect), VO2 max, FTP.

## Milestone 4 — Strava: deliberately skipped

Every Strava activity is the same Garmin recording synced over, with *less* sensor
detail. Skipping it removed the entire double-counting problem. Revisit only if
segment/PR analysis becomes interesting (the architecture still allows adding the
official Strava MCP alongside).

## Milestone 5 — weekly summaries + planning support

- `get_weekly_training_summary`: ISO-week totals from one paginated request (weekly
  TSS is impossible — Garmin's list API omits per-ride TSS — so Garmin training load
  is the summable signal; the tool says so).
- `get_training_plan_context`: FTP + VO2 + training status + 14 days of rides +
  recent sleep/HRV/RHR in one call.
- `plan_week` MCP prompt: encodes the required plan structure (purpose, duration,
  FTP-anchored intensity, intervals, easier alternative, rationale) and guardrails.

**Then:** the coach produced the 8-week Whistler plan
([whistler-gran-fondo-plan.md](../training/whistler-gran-fondo-plan.md)) from real
data — the key insight being that fitness (FTP 290, VO2 ~64) was already sufficient
and the gap was *sustained-effort specificity* (81% of ride time below 159 W with
heavy stop-go).

## Version control

Pushed to `github.com:anthonytrieu/training` (private single-user repo). The
`.gitignore` blocks tokens, `.env`, venvs, and build artifacts; fixtures are
sanitized. Commits carry no co-author trailer (owner preference).

## Milestone 6 — the web app

**Stack decision** (user choices in bold):
- **Chat via the Claude Agent SDK using the existing Claude Code subscription login**
  — no API key, no separate billing. The chat endpoint spawns a Claude agent that
  connects to the *same* `garmin-mcp` server, so tools exist in exactly one place.
- **Dashboard + chat** scope, model **Opus 4.8**.
- Backend: FastAPI (`src/garmin_coach/web/`) — dashboard endpoints are thin wrappers
  over the MCP tool functions (browser and Claude read identical data); typed Garmin
  errors map to HTTP 401/429/503; serves the built frontend with an SPA fallback.
- Frontend: Vite + React + TypeScript + Tailwind + shadcn/ui, Recharts for charts
  (palette validated with an accessibility checker: CVD separation, contrast,
  ordinal-ramp lightness), dark mode, sidebar layout.

**Pages:** Dashboard (stat tiles, weekly volume/load bars, wellness sparklines,
rides table) · Ride detail (synced power/HR/elevation streams, time-in-zone bars,
laps) · Plan (rendered markdown) · Coach (streaming chat with "Looking up recent
rides…" tool-activity lines).

**Bugs found by verifying, not assuming:**
- `tools=[]` in the Agent SDK removed the MCP tools too — and Claude Code 2.1+ defers
  MCP tool schemas behind a `ToolSearch` tool, so disallowing ToolSearch also hides
  every garmin tool. Fix: `disallowed_tools` list that strips bash/file/web tools but
  keeps ToolSearch, plus `strict_mcp_config` so the agent never sees other personal
  MCP servers.
- Starlette's `StaticFiles` raises (not returns) 404s, and FastAPI's `HTTPException`
  is a *subclass* of Starlette's — catching the child missed the parent, breaking the
  SPA fallback for direct URLs like `/plan`.
- Every page was screenshot-verified with headless Chromium (Playwright) against live
  data; the chat was verified with real multi-turn round-trips.

## Fueling planner (`/fuel`)

Inspired by Roadman Cycling / Rule 28 / CarbEngine / Nduranz calculators and the
glucose:fructose dual-transporter research. Entirely client-side
(`web/src/lib/fueling.ts`) — no AI cost.

- Encoded guidance: 30–60 g/h under 2 h, 60–90 g/h for 2–3 h, 90+ g/h beyond 3 h;
  >60 g/h needs dual-source carbs; >90 g/h needs gut training; fluid ≈ 80% of sweat
  rate capped at 1 L/h; sodium = sweat volume × concentration (default 950 mg/L).
- Output: a timed schedule (drink X ml / take Y every 15–30 min), per-hour tiles vs.
  targets, prep playbook with cost, and honest warnings (over-drinking vs. sweat loss,
  sodium shortfall, gut-training).
- Product DB with approximate labeled values; saved plans in localStorage; print/PDF;
  "Review with coach" hands the plan into the chat.

## Course-aware fueling + maple syrup

- The library has no course methods, but its authenticated passthrough does:
  `api.connectapi("/course-service/course")` returns all saved courses (verified live
  before planning). New `get_courses` MCP tool + `/api/courses` — always fetched
  live, so new courses appear as soon as they sync.
- The planner gained a course dropdown with a **transparent, editable duration
  estimate**: `hours = km / flat_speed + climb_m / climb_rate` (by intensity).
- **Maple syrup + plain water became the defaults** (the rider's actual practice):
  syrup ≈ 27 g carbs per 30 ml shot, sucrose → ~1:1 glucose:fructose (genuinely
  dual-source), near-zero sodium → salt-pinch guidance. The coach's system prompt
  learned all of this, so "how should I fuel Seymour Mountain?" fetches the course,
  estimates duration, and answers in syrup shots and bottles.

## Schedule tab (`/schedule`)

The 8-week plan was encoded as structured data
([whistler-sessions.json](../training/whistler-sessions.json)) — each week has ~4
sessions (title, kind, duration, power target, detail, easier alternative). The page
shows the current week's sessions as a **pool you drag (or tap) onto any day** —
replacing the fixed Tue/Thu/Sat/Sun rhythm with the rider's own weekly arrangement.
Assignments persist in localStorage; days overlay rides already recorded on Garmin;
race day is locked to Sep 12; "Review week with coach" sends the chosen layout to the
chat.

## Making it a phone app (private)

Decision: **keep everything on the Mac, reach it over Tailscale** — because a cloud
host would force an API key for chat (billing change), an auth layer, and moving
Garmin tokens off-machine.

- **PWA**: manifest + generated icons (bike + power bolt, rendered from SVG via
  headless Chromium) + standalone-display meta tags → installs from the phone home
  screen as a real app. No service worker (live data; offline caching buys bugs).
- **Mobile pass**: every page screenshot-checked at 390 px; fixes included
  dynamic-viewport chat height (`h-dvh`), scroll containers for tables, and
  truncating select labels (a long course name was forcing 158 px of overflow).
- **Always-on**: launchd LaunchAgent (`deploy/com.garmin-coach.web.plist`) starts the
  server at login and restarts it on crash (verified by killing it).
- **Network**: `tailscale serve --bg http://127.0.0.1:8787` — the server keeps its
  localhost-only binding; Tailscale proxies tailnet-HTTPS to it with automatic
  certificates. Result: `https://anthonys-macbook-air.tail08c005.ts.net`, reachable
  only by devices on the owner's tailnet (Mac + iPhone), invisible publicly.

---

## Final architecture

```
iPhone (PWA) ──Tailscale HTTPS──▶ Mac
                                   ├── launchd → garmin-coach-web (FastAPI, 127.0.0.1:8787)
                                   │     ├── /api/*  ── GarminClient ──▶ Garmin Connect (unofficial API)
                                   │     ├── /api/chat ── Claude Agent SDK (subscription login)
                                   │     │        └── spawns garmin-mcp (stdio) — same 20 tools
                                   │     └── serves web/dist (React SPA)
                                   ├── ~/.garminconnect  (OAuth tokens, never in repo)
                                   └── Claude Code login (chat auth)
```

## Working practices that shaped the result

1. **Verify before designing**: real API responses were captured before writing every
   normalizer; endpoints were probed live before being planned into features.
2. **Honesty as a feature**: unavailable data (readiness, recovery time, weekly TSS)
   says so explicitly instead of being estimated; Garmin-reported vs. locally
   calculated is labeled everywhere.
3. **One quarantine module** for the unofficial API; one source of truth for tools
   (MCP server functions reused by the web API).
4. **Verify by using, not by assuming**: headless-browser screenshots, live chat
   round-trips, kill-and-restart tests — several real bugs were found this way.
5. **Tests on sanitized real data**: 47 backend tests run against fixtures captured
   from the actual account with IDs/GPS scrubbed.
