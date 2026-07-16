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
4. Combine Garmin + Strava without double-counting.
5. Weekly summaries + adaptive rolling 7-day plan (no auto-scheduling to device).
