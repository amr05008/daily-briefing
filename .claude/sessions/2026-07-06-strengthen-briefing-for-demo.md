---
date: 2026-07-06
summary: Demo-readiness upgrade — NWS alerts, Headlines synthesis, quiet-feed consolidation, 26h window, push-time config validation, Krebs feed
tags: [briefing, prompt, ci, demo, youtube]
---

## Summary

Strengthened the briefing ahead of the YouTube video #1 demo ("Build a Personal Morning Briefing with Claude Code", per content-studio/youtube-launch.md). Five upgrades: NWS weather alerts, a synthesized Headlines message, quiet-feed consolidation, a 26-hour feed window, and push-time config validation via CI. Also added Krebs on Security to the feeds. All changes were adversarially reviewed (/grill via fresh-eyes subagent), which caught a prompt self-contradiction and a validator hole; both fixed and re-verified.

## Changes

- `briefing/config.json` — added Krebs on Security feed (verified live, max_items 3)
- `briefing/user-context.md` — added security to interests; fixed stale tone lines that contradicted prompt.md's Discord templates
- `briefing/prompt.md` —
  - New step 2b: NWS active alerts (`api.weather.gov/alerts/active?point=`), curl with User-Agent, 400-with-"out of bounds" = non-US skip vs other-400 = partial failure, retry-once on 5xx, max 3 alerts by severity, one line each; alerts render at top of weather message
  - Feed filter widened 24h → 26h (late runs can't silently drop posts); date edge cases specified (undated items excluded + partial failure, future-dated = new)
  - New Message 2 "Headlines": 2–3 cross-feed picks ranked by user-context interests with "why this matters" lines; `_Quiet today:_` and `_Unavailable:_` footnotes
  - Per-feed messages only for feeds with new content (quiet ≠ unavailable ≠ has-content, each with exactly one home)
  - Fixed pre-existing wrong config path (`config.delivery.discord_webhook.url`)
- `scripts/validate.py` (new) — stdlib-only config validator: JSON shape, coords, travel dates (incl. start ≤ end), feeds, delivery, IANA timezone; `--check-feeds` mode does live URL checks (404/410/DNS-failure = hard error; 403/429/5xx/timeout = warning, since CI IPs trip bot protection)
- `.github/workflows/validate.yml` (new) — runs the validator with `--check-feeds` on pushes/PRs touching briefing/, scripts/, or itself
- `README.md` — examples updated (alerts section, Headlines message), how-it-works list, CI validation note, repo structure

## Decisions

- **26h window over state-tracking**: agent is deliberately stateless (never touches git), so gap-coverage is done by overlap; occasional duplicate beats silent miss.
- **Validator severity split**: deterministic failures (bad JSON, dead URL, NXDOMAIN) fail CI; transient-looking ones (403/429/5xx/timeout) warn — a demo repo can't afford flaky red CI training people to ignore it.
- **Doc order headlines-first, Discord order weather-first** — deliberate: doc is read top-down (synthesis = executive summary), Discord arrives as a morning stream (weather = most immediately actionable).

## Notes

- Grill verdict was DON'T SHIP on first pass: step 3 still contained the old "No new posts today" instruction (contradicting the new quiet-feed design) and validate.py let DNS failures pass as warnings, falsifying the README's claim. Both fixed, re-verified by test.
- Stratechery token removed from config.json: feed URLs now support `$PLACEHOLDER` values resolved from the trigger's bootstrap prompt (same pattern as the webhook URL). prompt.md resolves them at run time (missing value → unavailable + step-6 alert, never printed to logs); validate.py accepts/skips them. Aaron updated the scheduled trigger (claude.ai/code/scheduled) in-session: added `STRATECHERY_FEED_URL=<real URL>` to the bootstrap prompt, and fixed the trigger text's stale references (step 7 → step 6, removed "archive push"). Note the coupling this revealed: **the hosted trigger text hard-references prompt.md step numbers — renumbering steps in prompt.md requires manually updating the trigger.** On rotation: Passport has no self-serve feed-URL reset, so Aaron decided (2026-07-06) to accept the residual risk of the old token in public git history rather than rotate via support email. The placeholder still keeps it out of the current config, the demo video, and viewer forks.
- NWS alerts verified live against Brooklyn coords (active alert present on 2026-07-06); Barcelona coords correctly return 400 "out of bounds".
