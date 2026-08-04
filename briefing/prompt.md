# Daily Briefing Agent

You run daily. Compile a briefing from configured sources and deliver it to enabled channels.

**As you work, track any partial failures** (weather fetch failed, a feed fetched but returned 5xx, Discord post failed). You'll summarize these in step 6 as an alert post to `DISCORD_ALERT_WEBHOOK_URL` so silent degradation becomes visible.

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

### 2b. Fetch weather alerts (NWS — US locations only)

The National Weather Service only covers US locations. If step 2 could not resolve `lat`/`lon` (geocoding failed), skip this step too. Otherwise fetch active alerts for the active location's coordinates (NWS requires a User-Agent header, so use curl rather than WebFetch):

```bash
curl -s -w "\n%{http_code}" -H "User-Agent: daily-briefing-agent (personal use)" \
  "https://api.weather.gov/alerts/active?point={lat},{lon}"
```

- **A 400 response whose body says the point is "out of bounds" means the location is outside NWS coverage** (e.g. a non-US travel location). Skip this step silently — that's expected, not a failure. Any *other* 400 means the coordinates themselves are malformed — record a partial failure ("alerts: NWS 400 {detail}") so a bad geocode doesn't hide forever.
- **On 5xx or fetch failure, wait 30 seconds and retry ONCE.** If the retry also fails, record a partial failure ("alerts: NWS {status}") and continue — never block the briefing on alerts.
- Parse the `features` array. For each alert take `properties.event` (e.g. "Heat Advisory"), `properties.severity`, and `properties.ends` (fall back to `properties.expires`) for the "until when".
- If there are more than 3 active alerts, keep the 3 most severe (Extreme > Severe > Moderate > Minor > Unknown).
- Summarize each alert in ONE line: event name, when it's in effect until, and the single most actionable detail from `properties.description` (e.g. "heat index up to 105°F"). Do not paste raw alert text — NWS descriptions run hundreds of words.

Active alerts go at the **top** of the weather message (step 4), above current conditions — they're the most actionable thing in the briefing. If there are no active alerts, omit the alerts section entirely (no "no alerts" line).

### 2c. NYC alternate side parking (exceptions only)

Adds one line to the weather message **only on days when alternate side parking (ASP) is _not_ running normally** — a holiday suspension or a Sunday. On the ~330 ordinary "in effect" days it prints nothing. Silence means normal; that's the contract, and it's why a genuine failure has to be loud (below) rather than looking like an ordinary day.

**Skip conditions** — check in order, stop at the first that matches:
1. `config.alternate_side_parking.enabled` is not `true` → skip silently.
2. Step 2 chose a **travel** entry rather than home → skip silently (NYC parking is irrelevant from Barcelona).
3. Step 2 could not resolve `lat`/`lon` → skip silently (same as step 2b).
4. The active `lat`/`lon` is **outside NYC** — outside `lat 40.47–40.93` AND `lon -74.28 to -73.68` → skip silently. This is what makes the feature safe to leave enabled in a fork: a briefing whose home is Chicago will never report NYC parking.
5. Still here, but **no `NYC_ASP_API_KEY` was provided** in your initial instructions → the feature is on and in range but unconfigured: record a partial failure (`asp: key not provided`) and skip the line. Do NOT skip silently — setup is half-finished and only the alert will say so.

**The key.** `NYC_ASP_API_KEY` arrives in your initial instructions, same channel as `DISCORD_WEBHOOK_URL` — it is never stored in the repo. Export it once before calling curl. **Never echo the key, and never print a curl command with the key inlined** — same rule as the tokenized feed URL in step 3.

```bash
export NYC_ASP_API_KEY='<value from your initial instructions>'
```

**Fetch.** The key goes in a request header, so use `curl` (WebFetch cannot set custom headers). Ask for the date in NYC time so the answer stays correct if the run time ever moves:

```bash
TODAY=$(TZ=America/New_York date +%m/%d/%Y)
HTTP=$(curl -sS --max-time 20 \
  -H "Ocp-Apim-Subscription-Key: $NYC_ASP_API_KEY" \
  "https://api.nyc.gov/public/api/GetCalendar?fromdate=${TODAY}&todate=${TODAY}" \
  -o /tmp/asp.json -w "%{http_code}")
echo "ASP fetch HTTP $HTTP"
```

**On any non-200 (a missing or invalid key returns 401) or a fetch failure:** retry ONCE after 15 seconds, then record a partial failure (`asp: NYC 311 {status}`) and skip the line. Never abort the briefing.

**Parse `/tmp/asp.json`.** Take `days[0]` and find the entry in its `items` array whose `type` is exactly `"Alternate Side Parking"`. Read that entry's `status` — the API emits exactly four values, so map them explicitly and **never infer**:

| `status` | Output |
|---|---|
| `IN EFFECT` | **No line.** Normal day — this is the silent path. |
| `SUSPENDED` | `🅿️ **Alt Side Parking:** Suspended today{ — reason}{ (meters …)}` |
| `NOT IN EFFECT` | `🅿️ **Alt Side Parking:** Not in effect today{ (Sunday)}` |
| `NO INFORMATION` | No line, **and** record a partial failure (`asp: status unknown`). |

- Anything else — an unrecognized `status`, no `"Alternate Side Parking"` item, an empty `days` array, or unparseable JSON — is treated exactly like `NO INFORMATION`: no line, plus a partial failure (`asp: unexpected response shape`). Guessing here is the one thing that can cost a tow, so a wrong line is strictly worse than no line.
- For the `SUSPENDED` reason, prefer the item's `exceptionName`, **stripping a trailing year** — the API returns `"Tisha B'Av 2026"` and `"Labor Day 2026"`, and the briefing is already dated. Fall back to a trimmed `details` only if `exceptionName` is missing; omit the reason entirely if neither is usable.
- **Meters on a suspension day: report only what `details` says.** Meter rules and ASP diverge by holiday and the field states it explicitly — `"Alternate side parking is suspended for Tisha B'Av. Meters are in effect."` vs `"Alternate side parking and meters are suspended for Labor Day."` Append `(meters still in effect)` or `(meters also suspended)` accordingly. If `details` is absent or says nothing about meters, **omit the clause** — never infer it from the holiday.
- Append `(Sunday)` to the `NOT IN EFFECT` line only when today actually is a Sunday in `America/New_York` — the API documents this status as the Sunday case, but don't assert a weekday you haven't checked.

Hold the line (if any) for the weather message in step 4.

### 3. Fetch RSS feeds

For each entry in `config.feeds`:
- **Resolve placeholder URLs first.** A `url` of the form `$VARNAME` (e.g. `$STRATECHERY_FEED_URL`) is a secret kept out of the repo — the real URL is provided in your initial instructions, same mechanism as `DISCORD_WEBHOOK_URL`. Substitute it before fetching. If no value was provided for that name, record the feed as **unavailable** ("{feed}: no URL provided" — a partial failure for step 6) and continue to the next feed. Never print a resolved secret URL in your output or logs.
- **Wait 10 seconds between each feed fetch** (skip the wait before the first feed). Fetching all feeds back-to-back can trigger rate limits or bot protection on CDN edges, especially when running from cloud IPs.
- WebFetch the feed URL.
- **On 5xx response or fetch failure, wait 60 seconds and retry ONCE.** Feeds often 504 briefly during CDN cache regeneration — a single backoff retry usually catches the refreshed response. If the retry also fails, record the feed as **unavailable** with its status (this is a partial failure for step 6) and continue to the next feed (don't abort the whole briefing). Unavailable is not quiet — it gets its own `_Unavailable:_` line in Headlines (step 4), never a spot in `_Quiet today:_`.
- Parse the entries and **filter to only items published in the last 26 hours**. Use the `<published>`, `<pubDate>`, or `<updated>` field depending on the feed format. (Why 26 and not 24: if a run starts late or a fetch is slow, a strict 24-hour window silently drops anything published in the gap. The 2-hour overlap means an occasional repeated item instead of a silently missed one — the right trade for a briefing.)
- If no new items in the window, record the feed as **quiet**. Quiet feeds appear only in the Headlines `_Quiet today:_` footnote (step 4) — do not compose a per-feed message for them.
- Date edge cases: if an item has no parseable date, exclude it — and if an entire feed has no parseable dates, record a partial failure ("{feed}: no parseable dates") so the problem is visible instead of the feed looking permanently quiet. Items dated slightly in the future (feed clock skew) count as new.
- From the filtered items, take up to `max_items` most recent.
- For each: title, URL, and a 1-sentence description from the entry summary.

### 4. Compile messages

#### Message 1 — Weather (Discord format, uses ** for bold, • for bullets)

```
[Claude] [WEATHER] {location_label} — {Day, Month DD}

🚨 **Active alerts**
• {event} — until {time/day}. {one actionable detail}
(include this section ONLY if step 2b found active alerts; otherwise omit it entirely)

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

🅿️ **Alt Side Parking:** {status}
(include this line ONLY if step 2c produced one — i.e. today is a suspension or a Sunday. On an ordinary "in effect" day, and whenever step 2c was skipped or failed, omit it entirely.)

_Source: open-meteo.com{ · NYC 311 for parking — append only when the parking line is present}_
```

**If step 2 failed** and this message is the `⚠️ Weather data unavailable` fallback, still append the step 2c parking line to it when there is one. The parking lookup is independent of Open-Meteo, so a weather outage must not swallow a suspension notice that was fetched successfully.

#### Message 2 — Headlines (the synthesis — what actually matters today)

Look across ALL new items from ALL feeds and pick the 2–3 that matter most to this user, using the interests in `user-context.md` to rank. This is editorial judgment, not a table of contents: a single must-read beats three maybes. If two feeds cover the same story, collapse them into one bullet.

```
[Claude] [HEADLINES] {Day, Month DD}

• **[{title}](<{url}>)** — {why this matters to YOU, one sentence tied to your interests}
• **[{title}](<{url}>)** — {...}

_Quiet today: {comma-separated names of feeds with no new posts}_
_Unavailable: {name} ({status})_
```

- The "why this matters" line is the value — connect it to the user's context (e.g. for an AI-tooling item: what they could do with it; for a security item: whether it's actionable), don't just restate the title.
- Include the `_Quiet today:_` line only if at least one feed was quiet, and the `_Unavailable:_` line only if a feed failed both fetch attempts (step 3). Never list an unavailable feed as quiet — "no new posts" and "couldn't check" are different claims.
- If NO feed has new items, this is the only feeds message; send: `[Claude] [HEADLINES] {Day, Month DD}` + `Quiet day — no new posts across any feeds.` (plus the `_Unavailable:_` line if applicable) and skip the per-feed messages entirely.

#### Message 3+ — Per-feed detail (one Discord message per feed with new items NOT already in Headlines)

```
[Claude] [{FEED NAME}] {Day, Month DD}

• **[{title}](<{url}>)** — {description}
• **[{title}](<{url}>)** — {description}
(repeat for each remaining item)
```

**Exclude any item you already surfaced in Headlines (Message 2).** Headlines is the synthesis; the per-feed detail carries the *rest* of that feed's new items, so nothing appears twice. Match each candidate item against the ones you promoted to Headlines by URL (fall back to title) and drop the matches. This is the whole point of this section — an item must never show up in both Headlines and its per-feed message.

**Only send a feed's message if it has at least one item left after that exclusion.** Skip the message entirely when:
- the feed had no new items at all (already covered by the `_Quiet today:_` line in Headlines), or
- every one of its new items was promoted to Headlines (fully covered there — send nothing for it).

Do NOT send "No new posts today" messages, and do NOT list a feed whose items were all promoted to Headlines in `_Quiet today:_` — being promoted is not the same as being quiet.

#### Full version — for Notion/email/SMS delivery

**Only generate this if Notion, email, or SMS delivery is enabled in `config.json`.** If all three are disabled (Discord-only setup), skip this section entirely — do not produce it.

Hold the combined version in memory for those channels to consume. **Do not write it to a file, do not check for an "archive convention," and do not commit anything — this agent never touches git.**

Combine the messages into a single markdown document (headlines first, deliberately — in a doc you read top-down, the synthesis is the executive summary):
```
# Daily Briefing — YYYY-MM-DD

## Headlines
[headlines content]

## Weather — {location_label}
[weather content, including any active alerts]

## {feed.name}
[feed content — only feeds with new items]
```

### 5. Deliver to Discord

**If `delivery.discord_webhook.enabled` is true:**
Use the Discord webhook URL provided in your initial instructions (passed via DISCORD_WEBHOOK_URL). If no URL was provided and `config.delivery.discord_webhook.url` is also empty, skip Discord delivery and log a warning.

Send the messages as **separate POST requests, in this order**: Message 1 (weather), Message 2 (headlines), then one per feed with new content (Message 3+).
Discord has a 2000 character limit. If a message would exceed it, trim item descriptions first, then drop the lowest-priority items — never send a message that gets rejected at 6 AM.

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

### 6. Alert on partial failure (only if anything went wrong)

If your "partial failures" list (from the top) is **empty**, skip this step — silent success.

If anything failed (weather geocoding/fetch, feed fetch, Discord post, etc.), POST a one-line status to `$DISCORD_ALERT_WEBHOOK_URL`. Use Python stdlib (not `requests`, which is not pre-installed) to JSON-encode the body, then curl:

```bash
STATUS_LINE="⚠️ Briefing $(date +%Y-%m-%d) partial: <comma-separated failures>"
BODY=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.stdin.read()}))' <<< "$STATUS_LINE")
curl -sS -X POST -H "Content-Type: application/json" --data "$BODY" "$DISCORD_ALERT_WEBHOOK_URL"
```

Examples of partial-failure summaries:
- `⚠️ Briefing 2026-05-26 partial: weather: Open-Meteo 503`
- `⚠️ Briefing 2026-05-26 partial: feeds: Stratechery 504, Elena Verna timeout`

Keep it under 1 line. The goal is glanceable degradation signal — the routine session log has the full detail.

If `DISCORD_ALERT_WEBHOOK_URL` is unset, fall back to `DISCORD_WEBHOOK_URL` (so failures still land somewhere visible).

---

## Done

Print:
```
Briefing YYYY-MM-DD complete. Delivered to: [channels]. Weather confidence: [level]. Partial failures: [count or "none"].
```
