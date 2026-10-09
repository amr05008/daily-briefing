---
date: 2026-10-09
summary: Added optional step 5b, a spoken mp3 of the briefing (ElevenLabs via OpenRouter) posted as a final [AUDIO] message, switched on by an OPENROUTER_API_KEY line in the trigger; also moved the parking key's export into its fetch command
tags: [briefing, voice, tts, openrouter, elevenlabs, discord, grill, trigger-coupling]
---

## Summary

The briefing can now end with a two-to-three-minute spoken version. The agent rewrites the posted messages for listening, renders them with ElevenLabs v4 Turbo (voice `george`) through OpenRouter as an mp3, and uploads it as `[Claude] [AUDIO] {date}` on the same webhook. It runs only when the trigger provides `OPENROUTER_API_KEY`, and the text messages never depend on it. Verified with a manual trigger run.

## Changes

- `briefing/prompt.md`
  - New step **5b**. It's lettered so the trigger's "step 6" reference keeps pointing at the alert step.
  - Step 2c: the key export now sits inside the fetch block.
- `README.md`: the `[AUDIO]` sample output, how-it-works item 9, and the optional `OPENROUTER_API_KEY` line in both startup-instructions notes.
- Hosted trigger (not in the repo): the owner added `OPENROUTER_API_KEY`, a dedicated key with a monthly cap.

Commits: `87e35cb` (squash of #7), `2093cc1` (squash of #8).

## Decisions

- **The key is the switch.** There's no config block, no length counter and no retry. Without the key the step skips silently, and deleting the line turns it off. The key's monthly cap is the only limit on spend that matters.
- **A separate final message**, not an attachment on Headlines, so the existing messages don't change.
- **mp3, not WAV.** About 1 MB per minute, against 7 MB for a 2.5-minute WAV, which is near Discord's 10 MB attachment limit.
- **Skip unless at least one step 5 post landed.** Then a dead webhook doesn't pay for audio that can't be delivered.

## Notes

- **Grill (fresh-eyes subagent): SHIP after two fixes.**
  - A download cut off partway can still report `200 audio/mpeg`, so the step also requires curl `rc=0` and a file over 20 KB.
  - The agent's shell calls don't share environment variables, so each key is exported in the same block as the command that uses it.
- **Manual run on 2026-10-09:** a 1,248-character script (a quiet day, with the weather fallback) became a 1.39 MB mp3. A webhook call **with a file attached answers 200**, not the 204 a text post gets; the step accepts any 2xx.
- **Open-Meteo is returning 429s** ("Daily API request limit exceeded"), likely because cloud routines share IP addresses and so share the daily limit. The 2026-10-09 scheduled run recovered on the retry; the manual run failed both tries and used the fallback. Watch for a pattern before adding a second weather source.
- **The parking export fix matches what the agent already does.** The scheduled agent had already merged the export into the fetch command on its own.
