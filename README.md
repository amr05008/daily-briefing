# Daily Briefing 

A self-hosted daily briefing powered by Claude Code scheduled agents ("Routines"). I switched to using this after testing digest tools such as OpenClaw.

Every morning at whatever time you decide, a Claude agent spins up in Anthropic's cloud, fetches weather and your RSS feeds, and posts a formatted briefing to Discord (or any channel you configure). No server to maintain, no subscription beyond Claude Code.

---

## What it looks like

A short stack of Discord messages arrives each morning:

**Weather** — active alerts first, then current conditions, today's forecast, cycling/activity outlook, confidence rating:
```
[Claude] [WEATHER] Brooklyn, NY — Saturday, March 28

🚨 Active alerts
• Wind Advisory — until 7 PM today. Gusts to 45 mph; secure loose outdoor objects.

🌡️ Current conditions (as of 6:02 AM ET)
• 33°F / 1°C, Clear skies
• Wind: NW 14 mph, gusts to 28 mph
• Humidity: 49%

📊 Today's forecast
• High: 45°F / 7°C — Low: 33°F / 1°C
• Conditions: Mostly sunny, NW winds 14–16 mph with gusts to 28 mph

🌧 Precipitation
• None expected today
• Next chance: 30% Monday night after 2 AM

🚴 Cycling outlook
• Cold start at 33°F / 1°C, warming to 45°F / 7°C — dress in layers
• Gusty NW winds 14–28 mph — significant headwind/crosswind depending on route
• Clear and sunny all day — good visibility, no precipitation risk

✅ Confidence: High — hourly and period forecasts are consistent

_Source: open-meteo.com_
```

**Headlines** — the agent reads everything across all your feeds and picks the 2–3 items that matter most to *you*, with a one-line reason why. Quiet feeds get a single footnote instead of their own "nothing today" message:
```
[Claude] [HEADLINES] Saturday, March 28

• Vibe coding SwiftUI apps is a lot of fun — Willison's minimal-prompting workflow maps directly onto how you build side projects with Claude
• Patch Tuesday, March Edition — two of the actively-exploited Windows flaws affect infra you run

Quiet today: Elena Verna, Pragmatic Engineer
```

**Feeds** — then one message per source that actually has new posts, no link previews:
```
[Claude] [SIMON WILLISON] Saturday, March 28

• Vibe coding SwiftUI apps is a lot of fun — Willison built two macOS apps using Claude with minimal prompting
• We Rewrote JSONata with AI in a Day, Saved $500K/Year — Case study of AI-assisted port to Go
...
```

---

## How it works

Claude Code lets you schedule remote agents on a cron schedule. Each run:

1. Anthropic's cloud clones this repo into an isolated environment
2. The agent reads `briefing/prompt.md` for instructions
3. It reads `briefing/user-context.md` to personalize the output
4. It fetches weather from [Open-Meteo](https://open-meteo.com) (global coverage, no API key, dual °F/°C) and active weather alerts from the [National Weather Service](https://www.weather.gov/documentation/services-web-api) (US locations; skipped gracefully elsewhere)
5. It fetches your configured RSS feeds and filters to posts from the last ~24 hours (26h window, so a slow or late run never silently drops a post)
6. It synthesizes a Headlines message — the 2–3 items across all feeds that matter most, ranked against your interests
7. It posts to Discord (or other configured channels)

No server, no cron job, no infrastructure. Just a repo and a trigger.

---

## Setup

### Prerequisites

- [Claude Code](https://claude.ai/code) account — **Pro plan or above required** for scheduled triggers. The free tier does not support them.
- GitHub account — repo can be public or private

### 1. Fork this repo

Fork to your own GitHub account. The trigger will clone it fresh on every run.

### 2. Edit `briefing/user-context.md`

This is the most important file — it's what makes the briefing *yours*. Describe:
- Your interests and what to prioritize in feeds
- Your weather priorities (e.g. cyclist = wind first, runner = humidity, etc.)
- Tone and format preferences

### 3. Edit `briefing/config.json`

```json
{
  "weather": {
    "location": "Your City, Country"
  },
  "feeds": [
    { "name": "Feed Name", "url": "https://example.com/feed", "max_items": 5 }
  ],
  "delivery": {
    "discord_webhook": {
      "enabled": true,
      "url": "YOUR_DISCORD_WEBHOOK_URL"
    }
  }
}
```

**Finding RSS feeds:** Most blogs and newsletters have a feed at `/feed` or `/atom.xml`. Substack newsletters are always at `https://yourpublication.substack.com/feed`.

**Private or tokenized feeds** (Stratechery Passport, paid Substacks, anything whose feed URL contains a personal access token): don't put the real URL in `config.json` — a tokenized URL *is* a credential, and anyone who can read your repo can read your paid feed as you. Use a `$PLACEHOLDER` instead:

```json
{ "name": "Stratechery", "url": "$STRATECHERY_FEED_URL", "max_items": 4 }
```

…and pass the real URL in the trigger's bootstrap prompt (step 5), exactly like the Discord webhook. The agent substitutes it at run time; the config validator skips placeholders.

**Config is validated on every push.** A GitHub Action (`.github/workflows/validate.yml`) checks that `config.json` parses, has the right shape, and that every feed URL actually resolves and responds — so a broken config turns CI red minutes after you push, instead of degrading tomorrow's 6 AM briefing. You can also run it locally before pushing:

```bash
python3 scripts/validate.py --check-feeds
```

### 4. Set up Discord delivery

1. In Discord, go to your channel → Edit Channel → Integrations → Webhooks → New Webhook
2. Copy the webhook URL
3. Set `delivery.discord_webhook.enabled: true` in `config.json` — **leave `url` empty**
4. Instead, add the URL to your trigger's bootstrap prompt (keeps it out of your public repo):

```
The repo has been cloned into your working directory.
Get today's date by running: date +%Y-%m-%d
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
STRATECHERY_FEED_URL=https://stratechery.passport.online/feed/rss/YOUR_TOKEN
Then read briefing/prompt.md and follow its instructions exactly.
```

(The `STRATECHERY_FEED_URL` line is only needed if you use a `$PLACEHOLDER` feed — one line per placeholder, named to match. You can also add `DISCORD_ALERT_WEBHOOK_URL=...` pointing at a separate channel if you want partial-failure alerts routed away from the briefing itself — if you skip it, alerts fall back to the main webhook.)

No bot setup, no OAuth — Discord webhooks are just HTTPS endpoints. Storing secrets in the trigger (not the repo) means you can keep your repo public without exposing them.

### 5. Create the scheduled trigger

Open Claude Code and run `/schedule`, or go to [claude.ai/code/scheduled](https://claude.ai/code/scheduled).

Create a new trigger with these settings:

| Setting | Value |
|---------|-------|
| Name | `Daily Briefing` |
| Schedule | `0 10 * * *` (6am ET — adjust for your timezone, cron is UTC) |
| Environment | Internet Access |
| Git source | Your fork's GitHub URL |
| Model | `claude-opus-4-8` |
| Tools | `Bash, Read, Write, Edit, Glob, Grep, WebFetch` |

**Bootstrap prompt** — the version from step 4, with your secret lines filled in:
```
The repo has been cloned into your working directory.
Get today's date by running: date +%Y-%m-%d
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
STRATECHERY_FEED_URL=https://stratechery.passport.online/feed/rss/YOUR_TOKEN
Then read briefing/prompt.md and follow its instructions exactly.
```
(Drop the `STRATECHERY_FEED_URL` line if you have no `$PLACEHOLDER` feeds.)

### 6. Test it

Hit "Run now" from [claude.ai/code/scheduled](https://claude.ai/code/scheduled). The agent takes 1–2 minutes to run. Check Discord to verify.

---

## Customizing

### Switch weather location (e.g. when traveling)

Leave `weather.location` set to your home city and add a time-boxed entry to `weather.travel`. The agent picks the first active entry (where today falls between `start`, if set, and `end` inclusive) and auto-reverts to home once `end` passes — no second push needed.

```json
"weather": {
  "location": "Brooklyn, NY",
  "lat": 40.6782,
  "lon": -73.9442,
  "travel": [
    { "location": "Amsterdam, Netherlands", "lat": 52.3676, "lon": 4.9041, "end": "2026-04-24" },
    { "location": "Tokyo, Japan", "lat": 35.6762, "lon": 139.6503, "start": "2026-06-10", "end": "2026-06-18" }
  ]
}
```

Dates are `YYYY-MM-DD` and interpreted in the agent's timezone. `start` is optional (omit for "starts immediately"); `end` is required and inclusive. Expired entries are ignored, so you can delete them whenever.

Weather is powered by [Open-Meteo](https://open-meteo.com) — free, no API key, global coverage, °F and °C. Open-Meteo queries by lat/lon, so each location entry includes `lat`/`lon`. If you omit them, the agent falls back to Open-Meteo's [geocoding endpoint](https://geocoding-api.open-meteo.com/v1/search?name=YOUR+CITY) to resolve a city name into coordinates — but pre-caching coords skips a round-trip and removes one more thing that can fail. Look up coords once for new destinations and paste them in. (Previously used wttr.in; switched 2026-05-26 after sustained per-IP 503s from the routine sandbox.)

### Change the time
Update the cron expression on your trigger. Cron runs in UTC — use [crontab.guru](https://crontab.guru) to convert. Remember to adjust in March (EDT, UTC-4) and November (EST, UTC-5).

### Add or remove feeds
Edit the `feeds` array in `config.json`. Feeds are filtered to the last ~24 hours automatically. Weekly newsletters are fine to include — on quiet days they just appear in the Headlines footnote (`Quiet today: ...`) instead of getting their own message.

### Change what the briefing focuses on
Edit `briefing/user-context.md` — the agent reads it on every run. No trigger changes needed.

### Change the format or add sections
Edit `briefing/prompt.md`. This is where the agent instructions live. You can add sections, change the tone, restructure the output — the agent will follow it.

---

## Adding delivery channels

| Channel | What's needed |
|---------|--------------|
| **Discord** | Webhook URL in the trigger's bootstrap prompt (see Setup step 4) — no connector needed |
| **Slack** | Same as Discord — Slack incoming webhooks work identically |
| **Email** | Connect an email MCP (Resend, etc.) at [claude.ai/settings/connectors](https://claude.ai/settings/connectors) |
| **SMS** | Connect a Twilio MCP at [claude.ai/settings/connectors](https://claude.ai/settings/connectors) |

---

## Repo structure

```
briefing/
  prompt.md          ← agent instructions (the "how")
  user-context.md    ← your personal context (the "who")
  config.json        ← feeds, weather, delivery channels (the "what")
scripts/
  validate.py        ← config sanity check (CI runs it on every push)
.github/workflows/
  validate.yml       ← the CI trigger for the check above
```
