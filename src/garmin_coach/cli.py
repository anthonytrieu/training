"""Verification CLI: `garmin-coach recent-rides [--limit N] [--json]`.

Milestone 1 proof that auth, fetching and normalization work end to end,
before any MCP wiring.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .client import GarminClient, GarminClientError
from .models import RideSummary
from .normalize import normalize_ride_summaries


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def _fmt_ride(index: int, ride: RideSummary) -> str:
    lines = [
        f"{index}. {ride.name} — {ride.start_time_local or '?'} ({ride.activity_type})",
        f"   {ride.distance_km if ride.distance_km is not None else '?'} km"
        f" | {_fmt_duration(ride.duration_s)}"
        f" | +{ride.elevation_gain_m if ride.elevation_gain_m is not None else '?'} m",
    ]
    sensors: list[str] = []
    if ride.avg_power_w is not None:
        power = f"avg power {ride.avg_power_w:.0f} W"
        if ride.normalized_power_w is not None:
            power += f" (NP {ride.normalized_power_w:.0f} W, Garmin-reported)"
        sensors.append(power)
    if ride.avg_hr_bpm is not None:
        hr = f"avg HR {ride.avg_hr_bpm:.0f}"
        if ride.max_hr_bpm is not None:
            hr += f" / max {ride.max_hr_bpm:.0f} bpm"
        sensors.append(hr)
    if ride.avg_cadence_rpm is not None:
        sensors.append(f"cadence {ride.avg_cadence_rpm:.0f} rpm")
    if sensors:
        lines.append("   " + " | ".join(sensors))
    return "\n".join(lines)


def cmd_recent_rides(limit: int, as_json: bool) -> int:
    try:
        client = GarminClient.from_saved_tokens()
        raw = client.recent_cycling_activities(limit=limit)
    except GarminClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    rides = normalize_ride_summaries(raw)
    if as_json:
        print(json.dumps([r.to_dict() for r in rides], indent=2))
        return 0

    if not rides:
        print("No cycling activities found on Garmin Connect.")
        return 0

    print(f"Most recent {len(rides)} cycling activities (source: Garmin Connect):\n")
    print("\n\n".join(_fmt_ride(i, r) for i, r in enumerate(rides, start=1)))
    return 0


def main() -> int:
    logging.getLogger("garminconnect").setLevel(logging.WARNING)
    logging.getLogger("garth").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(prog="garmin-coach", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    recent = sub.add_parser("recent-rides", help="Show the most recent cycling activities")
    recent.add_argument("--limit", type=int, default=5, help="Number of rides (default 5)")
    recent.add_argument("--json", action="store_true", help="Output normalized JSON")

    args = parser.parse_args()
    if args.command == "recent-rides":
        return cmd_recent_rides(limit=args.limit, as_json=args.json)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
