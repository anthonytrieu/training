# Architecture decisions

Single-user personal cycling assistant. Claude is the conversation/reasoning layer;
data access is split between the **official Strava MCP** (hosted, OAuth) and a
**local Garmin MCP server** built here.

## Decisions

1. **Claude as the interface; no custom frontend.** No UI is built until the MCP
   tooling works reliably in normal Claude usage.
2. **Local Garmin MCP server over python-garminconnect.** Garmin has no public
   consumer API; python-garminconnect wraps the unofficial web API. Consequences:
   - It can break without notice → every library call goes through
     `client.py`, the single quarantine module, and errors are mapped to typed,
     user-actionable exceptions (`ReauthRequiredError`, `RateLimitedError`,
     `GarminUnavailableError`).
   - Library method names are used exactly as they exist in the source (verified
     against v0.3.6); MCP tool names are simpler aliases.
3. **Credentials never touch the repo.** `garmin-setup` performs the interactive
   email/password/MFA login once; OAuth tokens persist to `~/.garminconnect`
   (outside the project) and auto-refresh. Nothing logs credentials or tokens.
4. **Read-only v1.** No write methods (upload, delete, schedule) are exposed. Workout
   creation comes later, behind an explicit confirmation step.
5. **Normalized models between Garmin and Claude.** Raw Garmin JSON is large and
   unstable. `normalize.py` produces compact models with explicit units in field
   names, ISO-8601 timestamps, `source` provenance (garmin/strava/calculated), and
   `None` for missing data instead of guesses. Garmin-reported values (e.g. Normalized
   Power) are labeled as reported, never silently recomputed.
6. **Single-sided power caveat is structural.** Rides with power carry a `power_note`
   stating the Rally RS100 doubles left-leg power, so no downstream analysis can claim
   L/R balance.
7. **No SQLite cache yet.** Added only if multi-week comparisons (Milestone 4–5)
   materially benefit or Garmin rate limits bite.
8. **Dedup rule for Garmin+Strava (Milestone 4):** match on start time (±2 min),
   duration and distance tolerance; prefer Garmin for sensor/recovery detail, Strava
   for its fitness trends and cross-sport analytics. Never double-count.

## Web app (Milestone 6)

Local dashboard + coach chat, decided 2026-07-16:

- **Backend**: FastAPI (`src/garmin_coach/web/`). Dashboard endpoints are thin wrappers
  over the MCP server's tool functions, so the browser and Claude read identical
  normalized data; typed Garmin errors map to 401/429/503. The built frontend is
  served statically with an SPA fallback.
- **Chat**: Claude Agent SDK (`claude-agent-sdk`) using the local Claude Code
  subscription login (user decision: no separate API billing), model
  `claude-opus-4-8`, streaming over SSE with tool-activity events. The agent is
  sandboxed to the garmin MCP server via `allowed_tools=["mcp__garmin"]`,
  `strict_mcp_config`, and a disallow-list of built-in tools. Gotcha discovered in
  verification: Claude Code 2.1+ defers MCP tool schemas behind `ToolSearch`, so
  `ToolSearch` must stay allowed and `tools=[]` must not be used — either hides all
  garmin tools.
- **Frontend**: Vite + React + TS + Tailwind + shadcn/ui, Recharts for charts (palette
  validated with the dataviz skill's checker), sidebar layout, dark mode. Chat UI is a
  small custom SSE component rather than assistant-ui: our SSE protocol is 4 event
  types, and a custom component was simpler than adapting assistant-ui's runtime.
- Single-user, 127.0.0.1 only, no auth. Verified end-to-end with headless-browser
  screenshots and live chat round-trips (multi-turn memory, real tool calls).

## Fueling planner (added 2026-07-16)

Client-side only (`web/src/lib/fueling.ts` + `web/src/pages/fuel.tsx`) — no backend or
AI cost. Inspired by Roadman Cycling, Rule 28, CarbEngine and Nduranz calculators.
Encoded guidance: carb targets by duration/intensity (30-120 g/h; >60 needs dual-source
glucose+fructose, >90 needs gut training — Jeukendrup dual-transporter model), fluid at
~80% of sweat rate capped at 1 L/h practical intake, sodium from sweat volume × mg/L
(default 950, typical 230-1600). Product database values are approximate and labeled as
such. Plans persist to localStorage; `planSummaryForCoach` hands the plan to the chat
for review against training data.

## Milestones

1. ✅ Local auth + five most recent cycling activities via CLI.
2. ✅ Expose recent rides through one MCP tool (`get_recent_activities` in
   `server.py`, FastMCP over stdio). Client login is lazy/cached so a dead Garmin
   session can't kill the server at startup; tool errors carry reauth ("run
   `garmin-setup`") or rate-limit guidance. Verified end-to-end with a live stdio
   MCP client.
3. ✅ Detailed ride analysis + recovery context — 13 more tools (15 total): activity
   summary/splits/zones/time-series, comparison, training status, readiness, HRV,
   sleep, resting HR, VO2 max, FTP. All normalizers were designed against captured
   real responses, and sanitized captures became the test fixtures. Findings from
   the real account:
   - Garmin records IF/TSS/FTP-at-ride-time in `summaryDTO` — exposed as
     Garmin-reported values, never recomputed locally.
   - Training readiness and recovery time are watch features; an Edge 540-only
     account gets none via Garmin Connect. Those tools return explicit
     `available: false` + explanation instead of estimates.
   - History tools (HRV/sleep/RHR) make one Garmin request per day; capped at
     14 days to respect rate limits.
4. ⏭ Skipped (user decision, 2026-07-16): Strava adds no ride data beyond what the
   Edge already records — every Strava activity is the synced Garmin ride. Skipping
   removes the whole double-counting problem. Revisit only if Strava segment/PR
   analysis (climbing) becomes interesting; the architecture still accommodates the
   official Strava MCP alongside this server.
5. ✅ Weekly summaries + planning support. `get_weekly_training_summary` aggregates
   ISO weeks locally from one paginated Garmin request (weekly TSS impossible: the
   activity list omits per-ride TSS; Garmin training load is the summable signal).
   `get_training_plan_context` bundles FTP/VO2/status/14-day rides/wellness into one
   call so planning doesn't need ten tool round-trips. The 7-day plan itself is
   produced by Claude via the `plan_week` MCP prompt, which encodes the required
   session structure (purpose, duration, FTP-anchored intensity, intervals, easier
   alternative, rationale) and guardrails (no invented zones, no L/R power claims,
   no medical diagnosis, no workout uploads).
