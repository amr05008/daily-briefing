#!/usr/bin/env python3
"""Validate briefing/config.json — run locally or in CI.

Usage:
  python3 scripts/validate.py               # structure checks only
  python3 scripts/validate.py --check-feeds # also verify each feed URL responds

Catches config mistakes at push time (when you're at a keyboard) instead of
at 6 AM (when the briefing silently degrades). Stdlib only — no installs.

Exit code 1 on hard errors (invalid JSON, missing keys, dead feeds).
Transient-looking feed failures (403/429/5xx/timeout) are warnings, not
errors — CI runner IPs often trip bot protection that the briefing agent's
environment doesn't.
"""

import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "briefing" / "config.json"
USER_AGENT = "daily-briefing-validator (config check; github.com/amr05008/daily-briefing)"

# Feed URLs may be "$VARNAME" placeholders for tokenized/private feeds; the real
# URL is supplied via the trigger's bootstrap prompt and never lives in the repo.
PLACEHOLDER_RE = re.compile(r"^\$[A-Z][A-Z0-9_]*$")

errors: list[str] = []
warnings: list[str] = []


def check_coords(entry: dict, label: str) -> None:
    has_lat, has_lon = "lat" in entry, "lon" in entry
    if has_lat != has_lon:
        errors.append(f"{label}: has one of lat/lon but not both")
        return
    if has_lat:
        lat, lon = entry["lat"], entry["lon"]
        if isinstance(lat, bool) or not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
            errors.append(f"{label}: lat must be a number in [-90, 90], got {lat!r}")
        if isinstance(lon, bool) or not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
            errors.append(f"{label}: lon must be a number in [-180, 180], got {lon!r}")


def check_date(entry: dict, key: str, label: str, required: bool) -> None:
    if key not in entry:
        if required:
            errors.append(f"{label}: missing required '{key}' (YYYY-MM-DD)")
        return
    try:
        date.fromisoformat(entry[key])
    except (TypeError, ValueError):
        errors.append(f"{label}: '{key}' must be YYYY-MM-DD, got {entry[key]!r}")


# Coarse NYC bounding box — the same gate briefing/prompt.md step 2c applies at
# run time. Keep the two in sync if either ever moves.
NYC_LAT = (40.47, 40.93)
NYC_LON = (-74.28, -73.68)


def in_nyc(entry: dict) -> bool:
    """True if entry's coords sit inside NYC. Unknown coords count as inside —
    the agent geocodes at run time, so we can't rule it out from here."""
    lat, lon = entry.get("lat"), entry.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return True
    return NYC_LAT[0] <= lat <= NYC_LAT[1] and NYC_LON[0] <= lon <= NYC_LON[1]


def check_structure(config) -> None:
    if not isinstance(config, dict):
        errors.append("config.json must be a JSON object at the top level")
        return
    weather = config.get("weather")
    if not isinstance(weather, dict):
        errors.append("missing 'weather' object")
    else:
        if not isinstance(weather.get("location"), str) or not weather["location"].strip():
            errors.append("weather.location must be a non-empty string")
        check_coords(weather, "weather")
        travel = weather.get("travel", [])
        if not isinstance(travel, list):
            errors.append("weather.travel must be an array")
            travel = []
        for i, trip in enumerate(travel):
            label = f"weather.travel[{i}]"
            if not isinstance(trip, dict):
                errors.append(f"{label}: must be an object")
                continue
            if not isinstance(trip.get("location"), str) or not trip["location"].strip():
                errors.append(f"{label}: 'location' must be a non-empty string")
            check_coords(trip, label)
            check_date(trip, "end", label, required=True)
            check_date(trip, "start", label, required=False)
            try:
                if date.fromisoformat(str(trip.get("start"))) > date.fromisoformat(str(trip.get("end"))):
                    errors.append(f"{label}: 'start' is after 'end' — this trip can never activate")
            except (TypeError, ValueError):
                pass  # missing/malformed dates already reported above

    asp = config.get("alternate_side_parking")
    if asp is not None:
        if not isinstance(asp, dict):
            errors.append("'alternate_side_parking' must be an object")
        elif not isinstance(asp.get("enabled"), bool):
            errors.append(
                "alternate_side_parking.enabled must be a boolean, got "
                f"{asp.get('enabled')!r} — a string like \"false\" reads as ON to the agent"
            )
        elif asp["enabled"] and isinstance(weather, dict) and not in_nyc(weather):
            # Not an error: the agent gates on the same box at run time and stays
            # silent. Say so once here so a fork doesn't wait for a line that
            # will never come.
            warnings.append(
                "alternate_side_parking is enabled but home is outside NYC — "
                "the agent will skip it silently"
            )

    feeds = config.get("feeds")
    if not isinstance(feeds, list) or not feeds:
        errors.append("'feeds' must be a non-empty array")
    else:
        seen_urls = set()
        for i, feed in enumerate(feeds):
            label = f"feeds[{i}]"
            if not isinstance(feed, dict):
                errors.append(f"{label}: must be an object")
                continue
            name = feed.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{label}: 'name' must be a non-empty string")
            else:
                label = f"feeds[{i}] ({name})"
            url = feed.get("url")
            if not isinstance(url, str) or not (
                url.startswith(("http://", "https://")) or PLACEHOLDER_RE.match(url)
            ):
                errors.append(
                    f"{label}: 'url' must be an http(s) URL or a $PLACEHOLDER name, got {url!r}"
                )
            elif url in seen_urls:
                errors.append(f"{label}: duplicate feed URL {url}")
            else:
                seen_urls.add(url)
            max_items = feed.get("max_items")
            if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items < 1:
                errors.append(f"{label}: 'max_items' must be a positive integer, got {max_items!r}")

    delivery = config.get("delivery")
    if not isinstance(delivery, dict) or not delivery:
        errors.append("missing 'delivery' object")
    else:
        for channel, settings in delivery.items():
            if not isinstance(settings, dict) or not isinstance(settings.get("enabled"), bool):
                errors.append(f"delivery.{channel}: must have a boolean 'enabled'")
        if not any(isinstance(s, dict) and s.get("enabled") for s in delivery.values()):
            warnings.append("no delivery channel is enabled — the briefing will run but go nowhere")

    tz = config.get("timezone")
    if not isinstance(tz, str):
        errors.append("'timezone' must be a string (e.g. America/New_York)")
    else:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(tz)
        except Exception:
            errors.append(f"'timezone' is not a valid IANA timezone: {tz!r}")


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read(2048)


def check_feeds(config: dict) -> None:
    for feed in config.get("feeds", []):
        if not isinstance(feed, dict):
            continue
        name, url = feed.get("name", "?"), feed.get("url")
        if isinstance(url, str) and PLACEHOLDER_RE.match(url):
            print(f"  skipped (placeholder, resolved at run time): {name}")
            continue
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue  # already reported by check_structure
        for attempt in (1, 2):
            try:
                status, body = fetch(url)
                head = body.lstrip()[:200].lower()
                if not (head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head):
                    warnings.append(f"{name}: {url} responded but doesn't look like RSS/Atom")
                else:
                    print(f"  ok: {name}")
                break
            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    errors.append(f"{name}: feed URL is dead ({e.code}) — {url}")
                    break
                if attempt == 1:
                    time.sleep(10)
                    continue
                warnings.append(f"{name}: HTTP {e.code} from {url} (may be bot protection on CI IPs)")
            except urllib.error.URLError as e:
                # DNS failure is deterministic — a typo'd domain, not a flaky network.
                if isinstance(e.reason, socket.gaierror):
                    errors.append(f"{name}: DNS lookup failed for {url} — dead domain or typo")
                    break
                if attempt == 1:
                    time.sleep(10)
                    continue
                warnings.append(f"{name}: could not reach {url} ({e.reason})")
            except Exception as e:
                if attempt == 1:
                    time.sleep(10)
                    continue
                warnings.append(f"{name}: could not reach {url} ({e})")


def main() -> int:
    try:
        config = json.loads(CONFIG_PATH.read_text())
    except FileNotFoundError:
        print(f"ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: config.json is not valid JSON: {e}", file=sys.stderr)
        return 1

    check_structure(config)
    if "--check-feeds" in sys.argv and not errors:
        print("Checking feed URLs...")
        check_feeds(config)

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"config.json OK ({len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
