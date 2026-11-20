---
date: 2026-11-19
summary: Removed step 5b, the spoken mp3 version, because it went unused; took the OPENROUTER_API_KEY line out of the hosted trigger, and the owner disabled the key on OpenRouter
tags: [briefing, voice, openrouter, trigger-coupling, revert]
---

## Summary

The briefing is back to text only. The audio version added on 2026-10-09 wasn't getting listened to, so its daily TTS charge bought nothing. The repo revert merged as #9. The hosted trigger lost its `OPENROUTER_API_KEY` line, and that alone turned the step off.

## Changes

- `briefing/prompt.md`: step 5b removed. No other step was renumbered, so the trigger's "step 6" reference still holds.
- `README.md`: the `[AUDIO]` sample, how-it-works item 9, and the two `OPENROUTER_API_KEY` notes removed. The documented model now matches the live trigger (`claude-opus-5-5`).
- Hosted trigger (not in the repo): the `OPENROUTER_API_KEY` line removed with RemoteTrigger (get, then a full `job_config` update). Nothing else changed.
- OpenRouter: the owner disabled the dedicated key.

Commits: `4908637` (squash of #9, a revert of #7's `87e35cb`).

## Decisions

- **Revert rather than switch it off.** Leaving step 5b in place and dropping only the key would also have stopped the spend. The prompt would still have carried about 70 lines that every run reads and then skips. #8's parking-key fix touched step 2c only, so it survived the revert.
- **On demand instead of daily.** If a spoken briefing is wanted again, ask an agent for one that day (the `speak` skill covers that) rather than paying for one every morning.

## Notes

- To restore it, revert `4908637` and put a new OpenRouter key line back in the trigger. The 2026-10-09 log has the original design notes.
