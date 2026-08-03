# Daily Briefing Agent

You run daily. Compile a briefing from configured sources and deliver it to enabled channels.

**As you work, track any partial failures** (weather fetch failed, a feed fetched but returned 5xx, archive push failed, Discord post failed). You'll summarize these in step 8 as an alert post to `DISCORD_ALERT_WEBHOOK_URL` so silent degradation becomes visible.

---

## Steps

### 1. Read config

Read `briefing/config.json` and `briefing/user-context.md`.
Use the user context throughout — let it guide what you emphasize, how you frame info, and tone.

### 2. Fetch weather (Open-Meteo)

**Pick the active location.** Default to `config.weather` (home — uses `location`, `lat`, `lon`). If `config.weather.travel` exists, scan it for an entry where `end >= today` AND (`start` is absent OR `start <= today`). If one matches, use that entry's `location`/`lat`/`lon` instead — this is the active entry for the rest of the briefing. If multiple match, use the first. Print which location was chosen and why (home vs. travel entry).

**Resolve lat/lon.**
- If the active entry has `lat` and `lon`, use them directly (the common case).
- If `lat`/`lon` is missing, hit Open-Meteo's geocoding endpoint: `https://geocoding-api.open-meteo.com/v1/search?name={URL-encoded location}&count=1&language=en&format=json`. Use `results[0].latitude` and `results[0].longitude`. If geocoding fails or returns no results, record a partial failure ("weather: geocoding {location} failed") and skip the rest of step 2.

**Fetch the forecast.** Build the URL:
```
https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m&daily=temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_probability_max,weather_code&hourly=precipitation_probability,temperature_2m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1
```

WebFetch that URL. **On 5xx response or fetch failure, wait 30 seconds and retry ONCE.** If the retry also fails, set the weather message to `⚠️ Weather data unavailable — Open-Meteo returned {status} on two attempts. Please check weather manually.`, record a partial failure ("weather: Open-Meteo {status}"), and skip the rest of step 2 (still proceed with feeds and delivery — don't abort the briefing).

**Extract from the response:**
- Current conditions (`current`): `temperature_2m` (F), `apparent_temperature` (F, "feels like"), `relative_humidity_2m` (%), `weather_code` (WMO code — map below), `wind_speed_10m` (mph), `wind_direction_10m` (degrees — convert to 16-point compass), `wind_gusts_10m` (mph).
- Today's forecast (`daily`, index 0): `temperature_2m_max` (F high), `temperature_2m_min` (F low), `uv_index_max`, `precipitation_probability_max` (%), `weather_code` (today's overall).
- Hourly precipitation (`hourly.precipitation_probability`): 24-element array starting at midnight local time. Pick out a few hourly chances spanning the day (e.g. morning/midday/afternoon/evening) for the "Hourly chance" line.

**WMO weather code → text.** The API returns numeric codes; translate:
- `0` Clear · `1` Mainly clear · `2` Partly cloudy · `3` Overcast
- `45`, `48` Fog
- `51`, `53`, `55` Drizzle (light/moderate/dense)
- `56`, `57` Freezing drizzle
- `61`, `63`, `65` Rain (light/moderate/heavy)
- `66`, `67` Freezing rain
- `71`, `73`, `75` Snow (light/moderate/heavy) · `77` Snow grains
- `80`, `81`, `82` Rain showers (light/moderate/violent)
- `85`, `86` Snow showers
- `95` Thunderstorm · `96`, `99` Thunderstorm with hail

**Wind direction conversion.** Map degrees → 16-point compass (N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW). Formula: `index = round(degrees / 22.5) mod 16`.

**Dual-unit temperature display.** Open-Meteo returns Fahrenheit only (per our `temperature_unit=fahrenheit` param). Always display both: `°F / °C`. Convert: `C = round((F - 32) * 5/9)`.

Also synthesize a **Cycling outlook** (3 bullet points) using `user-context.md`:
- Temp context with both units (e.g. "Cold start at 33°F / 1°C, warming to 45°F / 7°C")
- Wind impact on cycling (e.g. "Gusty NW winds — expect headwind/crosswind depending on route")
- Visibility/conditions summary

Rate **Confidence: High / Medium / Low** based on hourly forecast consistency (look at how flat or variable `hourly.precipitation_probability` and `hourly.temperature_2m` are across the day). One sentence of reasoning.

### 3. Fetch NYC Alternate Side Parking status (optional — NYC home only)

A one-line "rules in effect / suspended" status for NYC alternate side parking (ASP), appended to the weather message (step 5).

**Skip conditions** (decide up front):
- If `config.alternate_side_parking.enabled` is not `true` → skip silently (feature is off): no line, no partial failure.
- Else if the active weather location chosen in step 2 is a **travel** entry → skip silently (ASP is irrelevant away from NYC): no line, no partial failure.
- Else if **no NYC 311 key was provided** in your initial instructions (see below) → the feature is enabled but misconfigured: skip the line but **record a partial failure** (`asp: key not provided`) so step 8 surfaces it. Do NOT skip silently here — the whole point of enabling it is to get the line.

Otherwise, fetch today's status from NYC's official 311 calendar API.

**The key.** The NYC 311 subscription key is provided in your initial instructions as `NYC_ASP_API_KEY` (same channel as `DISCORD_WEBHOOK_URL` — it is never stored in the repo). Make it available to the shell before calling curl: if it is not already exported as an env var, export it first from the value in your instructions:

```bash
export NYC_ASP_API_KEY='<value from your initial instructions>'
```

**Fetch.** The API requires the key as a request header, so use `curl` via Bash (WebFetch can't set custom headers). Query in NYC time so the date is correct even if the run time ever moves off the 6am ET schedule:

```bash
TODAY_US=$(TZ=America/New_York date +%m/%d/%Y)
HTTP=$(curl -sS --max-time 20 \
  -H "Ocp-Apim-Subscription-Key: $NYC_ASP_API_KEY" \
  "https://api.nyc.gov/public/api/GetCalendar?fromdate=${TODAY_US}&todate=${TODAY_US}" \
  -o /tmp/asp.json -w "%{http_code}")
echo "ASP fetch HTTP $HTTP"
```

**On a non-200 status, a body containing `"statusCode": 401` (missing/invalid key), or a fetch failure:** wait 15 seconds and retry ONCE. If it still fails, record a partial failure (`asp: NYC 311 {status}`), skip the ASP line, and continue to feeds — do not abort the briefing.

**Parse `/tmp/asp.json`.** The response has a `days` array; take the first element (today) and search its `items` array for the item whose `type` is `"Alternate Side Parking"`. Map its `status` field **explicitly** — these are the only valid values, so do NOT collapse "anything that isn't IN EFFECT" into "suspended" (a wrong "Suspended" can cost a ticket/tow):
- `"IN EFFECT"` → `🅿️ **Alternate Side Parking:** In effect today`
- `"SUSPENDED"` → `🅿️ **Alternate Side Parking:** Suspended today{ — reason}` — for the reason, prefer the item's `exceptionName` (short, e.g. "Passover"); fall back to a trimmed `details` only if `exceptionName` is absent; omit the reason entirely if neither is usable.
- `"NOT IN EFFECT"` → `🅿️ **Alternate Side Parking:** Not in effect today` (a normal off-day, e.g. Sunday — do **not** word this as "suspended")
- `"NO INFORMATION"`, any unrecognized value, or a missing ASP item / unreadable JSON → **do not guess** (rendering "Suspended" when the true state is unknown is the dangerous direction): skip the line and record a partial failure (`asp: status unknown` or `asp: unexpected response shape`).

Hold the resulting one-liner (if any) for the weather message (step 5). Nothing is posted in this step.

### 4. Fetch RSS feeds

For each entry in `config.feeds`:
- **Wait 10 seconds between each feed fetch** (skip the wait before the first feed). Fetching all feeds back-to-back can trigger rate limits or bot protection on CDN edges, especially when running from cloud IPs.
- WebFetch the feed URL.
- **On 5xx response or fetch failure, wait 60 seconds and retry ONCE.** Feeds often 504 briefly during CDN cache regeneration — a single backoff retry usually catches the refreshed response. If the retry also fails, note "Feed unavailable ({status} error). No content delivered." for that feed and continue to the next feed (don't abort the whole briefing).
- Parse the entries and **filter to only items published in the last 24 hours** (published date >= yesterday at the same time). Use the `<published>`, `<pubDate>`, or `<updated>` field depending on the feed format.
- If no new items since yesterday, note "No new posts today" for that feed — do not skip the feed section entirely.
- From the filtered items, take up to `max_items` most recent.
- For each: title, URL, and a 1-sentence description from the entry summary.

### 5. Compile messages

#### Message 1 — Weather (Discord format, uses ** for bold, • for bullets)

```
[Claude] [WEATHER] {location_label} — {Day, Month DD}

🌡️ **Current conditions** (as of {time} ET)
• {temp}°F, {sky conditions}
• Wind: {speed and direction, or "— (not reported)"}
• Humidity: {humidity}%

📊 **Today's forecast**
• High: {high}°F / Low: {low}°F
• Conditions: {detailed forecast including wind}

🌧 **Precipitation**
• {summary line}
• Hourly chance: {detail}

🚴 **Cycling outlook**
• {temp bullet}
• {wind bullet}
• {visibility/conditions bullet}

{✅ or ⚠️} **Confidence: {High/Medium/Low}** — {one-line reasoning}

{🅿️ ASP line from step 3 — include this line ONLY if step 3 produced one; omit entirely if the step was skipped or failed}

_Source: open-meteo.com{ · NYC 311 for parking — append only when the ASP line is present}_
```

#### Message 2 — Feeds (one Discord message per feed that has new content)

```
[Claude] [{FEED NAME}] {Day, Month DD}

• **[{title}](<{url}>)** — {description}
• **[{title}](<{url}>)** — {description}
(repeat for each new item; if no new items, send "No new posts today.")
```

Send one separate POST per feed.

#### Full version — for repo archive

Combine both messages into a single markdown file:
```
# Daily Briefing — YYYY-MM-DD

## Weather — {location_label}
[weather content]

## {feed.name}
[feed content]
```

### 6. Archive to repo

Write the full version to `briefing/output/YYYY-MM-DD.md`.
```bash
git config user.email "briefing-agent@scheduled"
git config user.name "Briefing Agent"
git add briefing/output/YYYY-MM-DD.md
git commit -m "briefing: YYYY-MM-DD"
git push origin main
```
If push fails for any reason, skip silently and continue.

### 7. Deliver to Discord

**If `delivery.discord_webhook.enabled` is true:**
Use the Discord webhook URL provided in your initial instructions (passed via DISCORD_WEBHOOK_URL). If no URL was provided and `config.discord_webhook.url` is also empty, skip Discord delivery and log a warning.

Send Message 1 (weather) and Message 2 (feeds) as **separate POST requests** — one per message.
Discord has a 2000 character limit; keep each message under that limit.

For each message, write payload to a temp file and POST:
```python
import json
msg = "MESSAGE CONTENT HERE"
with open("/tmp/discord_msg.json", "w") as f:
    f.write(json.dumps({"content": msg}))
```
```bash
curl -s -o /tmp/discord_response.txt -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d @/tmp/discord_msg.json \
  "WEBHOOK_URL_FROM_CONFIG"
```
Log the HTTP status code for each. 204 = success. If not 204, print response body.

**If `delivery.notion.enabled` is true:**
Use Notion MCP — search for parent page matching `parent_search_query`, create child page titled YYYY-MM-DD with full briefing content.

**If `delivery.email.enabled` is true:**
Use email MCP to send full version as HTML. (Skip if connector unavailable.)

### 8. Alert on partial failure (only if anything went wrong)

If your "partial failures" list (from the top) is **empty**, skip this step — silent success.

If anything failed (weather geocoding/fetch, feed fetch, archive push, Discord post, etc.), POST a one-line status to `$DISCORD_ALERT_WEBHOOK_URL`. Use Python stdlib (not `requests`, which is not pre-installed) to JSON-encode the body, then curl:

```bash
STATUS_LINE="⚠️ Briefing $(date +%Y-%m-%d) partial: <comma-separated failures>"
BODY=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.stdin.read()}))' <<< "$STATUS_LINE")
curl -sS -X POST -H "Content-Type: application/json" --data "$BODY" "$DISCORD_ALERT_WEBHOOK_URL"
```

Examples of partial-failure summaries:
- `⚠️ Briefing 2026-05-26 partial: weather: Open-Meteo 503`
- `⚠️ Briefing 2026-05-26 partial: feeds: Stratechery 504, Elena Verna timeout`
- `⚠️ Briefing 2026-05-26 partial: archive push failed (403)`

Keep it under 1 line. The goal is glanceable degradation signal — the routine session log has the full detail.

If `DISCORD_ALERT_WEBHOOK_URL` is unset, fall back to `DISCORD_WEBHOOK_URL` (so failures still land somewhere visible).

---

## Done

Print:
```
Briefing YYYY-MM-DD complete. Delivered to: [channels]. Weather confidence: [level]. Partial failures: [count or "none"].
```
