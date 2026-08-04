---
date: 2026-08-04
summary: Added NYC alternate-side-parking exceptions to the weather message via the 311 calendar API, as step 2c so no step numbers moved
tags: [briefing, nyc, api, reliability, trigger-coupling]
---

## Summary

The briefing now flags days when NYC alternate side parking isn't running normally — a holiday
suspension or a Sunday — and says nothing on the ~330 ordinary "in effect" days. Sourced from
NYC's official 311 GetCalendar API and verified end-to-end against live responses. Landed as
step **2c** rather than a new numbered step, which is what let it merge cleanly and kept the
hosted trigger working. Supersedes PR #5 (closed unmerged); shipped as PR #6.

## Changes

- `briefing/prompt.md` — new step 2c: gated fetch (enabled → home-not-travel → coords resolved →
  inside NYC box → key present), `today_id` date cross-check, explicit 4-value status map, meter
  clause read from `details`, year stripped from `exceptionName`. Weather message template gains a
  conditional parking line, including on the weather-failure fallback message.
- `briefing/config.json` — `alternate_side_parking` block (`enabled: true` + note).
- `scripts/validate.py` — validates the new block (non-boolean `enabled` is an error, since a
  string `"false"` reads as ON to the agent); `in_nyc()` helper warns when enabled with an
  out-of-box home.
- `README.md` — sample output, how-it-works item 5, a Customizing subsection, bootstrap-prompt
  notes, and a cron correction (`0 10` → `15 10`, matching the live trigger).
- `.gitignore` — Python build artifacts (a `.pyc` rode into #6 on a `git add -A`; untracked in
  `ae715a4`).
- Hosted "Daily Briefing" trigger (not in the repo) — added `NYC_ASP_API_KEY` to the bootstrap prompt.

Commits: `cadc9cf` (squash-merge of #6) → `ae715a4` (pycache) → `35a8b43` (cron doc fix).

## Decisions

- **311 API over the @NYCASP Twitter feed**, despite twitter-watcher already existing. Pulled the
  account's real history: the "rules are in effect today" post lands at **7:30am ET**, after the
  6:15am briefing, and there is **no tweet at all for Sundays** (verified across Jul 12/19/26 and
  Aug 2). Only the prior day's 4pm "tomorrow" tweet is available at run time. It also wouldn't have
  been less plumbing — the trigger has no MCP tools, so it would have gone over HTTP to the Worker's
  `/api/account-tweets` behind `X-Trigger-Token`: a new bootstrap secret either way, plus a paid
  twitterapi.io call daily. No NYC Open Data dataset exists for this (searched the Socrata catalog).
- **Step 2c, not a new step 3.** PR #5 inserted ASP as step 3 and renumbered everything after it,
  which left it `CONFLICTING` and would have silently broken the trigger's hardcoded "step 6"
  reference. Lettered sub-steps are now the pattern for anything added mid-prompt.
- **Exceptions-only output.** A daily "in effect today" line is wallpaper; the line's presence is
  the signal. Accepted trade-off: on a normal day, "no line" and "feature off" look identical, so
  every real failure path is loud instead.
- **Coarse NYC bounding box as the fork guard**, so a fork elsewhere skips silently rather than
  needing `enabled: false`. Rejected a NJ carve-out — no rectangle separates Jersey City (-74.04)
  from lower Manhattan (-74.02).
- **Never guess a status.** Unknown/missing/unparseable all skip the line and record a partial
  failure. A wrong "Suspended" is the direction that gets a car towed.

## Notes

- **The grill caught a bug the test harness structurally couldn't.** Skip condition 4 originally
  read "outside lat range AND outside lon range", which only skips when *both* bounds fail — Salt
  Lake City and Thessaloniki would have been treated as NYC. `validate.py` and the Python harness
  both had the correct and-of-inclusions; the defect existed **only in the English the agent reads**.
  Lesson: a harness that reimplements prompt logic in code validates the reimplementation, not the
  prompt. A case set built to fail exactly one bound put the old wording at 3 wrong of 11.
- **The hosted trigger is editable in-session** via the `RemoteTrigger` tool (`list`/`get`/`update`)
  — prior notes claimed only Aaron could change it. `update` needs a *full* `job_config`; a partial
  body drops `session_context` (allowed_tools, model, sources). Always `get` first.
- **Two API details only live data revealed:** `exceptionName` carries a trailing year
  (`"Labor Day 2026"`), and `details` *does* distinguish meter rules per-day — Tisha B'Av suspends
  ASP while "Meters are in effect", Labor Day suspends both. An earlier claim that the endpoint
  couldn't distinguish them was wrong.
- Verified against live payloads for 2026-08-04 (ordinary → no line), 08-02 (Sunday), 07-23
  (Tisha B'Av), 09-07 (Labor Day). Next time the line actually appears is **Labor Day, Sep 7**.
- Known limit: the box reaches west to `-74.28` for Staten Island, so a Newark/Jersey City home
  reads as in-range and gets a daily no-key alert until `enabled: false`. Documented; the validator
  warns before it ever reaches a 6am run.
- `IN EFFECT` days are silent by design, so a green run produces no parking output — do not read
  absence as breakage.
