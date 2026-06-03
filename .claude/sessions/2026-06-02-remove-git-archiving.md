---
date: 2026-06-02
summary: Removed git archiving from the briefing agent and cleaned up 37 orphan branches it had created
tags: [briefing, reliability, git, cleanup]
---

## Summary

Diagnosed and fixed the root cause of 37 stale `claude/*` remote branches: the scheduled
briefing agent committed each day's output and ran `git push origin main`, but the push had been
failing silently (a `403`) for ~May 2–29, so the harness preserved each run's sandbox branch.
Removed git archiving from the agent entirely (Discord delivery is the record), which eliminates
the push, the push-failure, and the branch litter in one move. Verified end-to-end with a live
scheduled run: Discord delivered, and zero git footprint (no commit, no branch).

## Changes

- `briefing/prompt.md` — deleted Step 5 "Archive to repo" (the `git commit`/`push` block),
  renumbered remaining steps to 1–6, dropped archive references from failure tracking, and made
  the full-version generation conditional on Notion/email/SMS being enabled (with an explicit
  "never touch git / don't write files" instruction).
- `README.md` — removed the archive step from "How it works", the `briefing/output/` verify
  reference, and the `output/` entry in the repo-structure tree.
- `briefing/output/` — deleted entirely (29 files, recoverable from git history).
- `docs/superpowers/specs/2026-06-02-remove-git-archive-design.md` — design spec.
- `docs/superpowers/plans/2026-06-02-remove-git-archive.md` — implementation plan.
- Remote: deleted 37 stale `claude/*` branches via `git push origin --delete`.

Commits: `af6d57f` `f66c4f8` (spec) → `73b6409` `9eaa0f9` `16d8d3f` `40a9d7e` (impl) →
`e40010a` (merge) → `bce92c8` (straggler removal) → `a08bdd3` (full-version follow-up).

## Decisions

- **Remove archiving rather than make the push robust.** Considered moving the archive to a
  separate branch/repo (B) and adding `git pull --rebase` + retry (C). Both keep machinery for
  something the user confirmed they don't need — Discord is the only enabled channel and is
  sufficient. Removal kills the whole problem class.
- **Deleted the orphan branches without harvesting their output files.** They held the only git
  copy of the May 2–29 briefings, but they're auto-generated daily artifacts the user doesn't
  archive — accepted the loss.
- **Declined the dead-man's-switch / heartbeat (item #1).** A daily briefing that doesn't show up
  in Discord is its own alarm; an external heartbeat would be redundant.

## Notes

- `zsh` does not word-split unquoted variables — bulk `git push origin --delete $branches` failed
  twice until piped through `xargs`.
- Mechanism confirmed by the data: successful-push days leave no branch; only failed pushes strand
  a commit that the harness preserves as a `claude/*` branch.
- Branch-sweep automation was deferred and is now unnecessary — with no git writes, no branches
  are created. Revisit only if branches reappear.
- The broader reliability backlog still has open items if ever wanted: audit remaining "silent
  skips" in the prompt (Discord/email), pin `TZ=America/New_York` for the date (config already
  has a `timezone` field the prompt could read), idempotent re-runs, and a dry-run mode.
