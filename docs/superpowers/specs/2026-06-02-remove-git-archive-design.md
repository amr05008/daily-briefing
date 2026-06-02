# Design: Decouple the briefing archive from git

**Date:** 2026-06-02
**Status:** Approved, pending implementation plan
**Topic:** Stop the scheduled briefing agent from writing artifacts to git (item #2 of the reliability improvements)

## Problem

The daily-briefing agent runs as a Claude Code scheduled remote agent (Routine). Each run
commits the day's output to `briefing/output/YYYY-MM-DD.md` and runs `git push origin main`.

This caused a sustained, invisible failure:

- For ~May 2–29 2026 the push to `main` was failing (the prompt's own alert example cites a
  `403` — a permission/auth rejection). The last agent-authored `briefing:` commit on `main`
  is 2026-04-30.
- The prompt said *"If push fails for any reason, skip silently and continue,"* so nobody noticed.
- The Routine harness preserves stranded local commits by pushing the run's sandbox branch
  (`claude/<slug>`) to origin. One orphan branch accumulated per failed day — 37 in total,
  cleaned up on 2026-06-02.

Writing append-only daily artifacts back to the same `main` the agent clones from is the root
design smell. The user confirmed the archive isn't needed (Discord delivery is sufficient), so
the fix is to remove git archiving entirely rather than make the push robust.

## Decision

Remove git archiving from the agent. After this change the agent fetches data, posts to Discord
(and any other enabled delivery channel), and exits — it never touches git.

### Approaches considered

- **A — Remove git archiving entirely (chosen).** Eliminates the whole problem class.
- **B — Move the archive to a separate `archive` branch or repo.** Rejected: more machinery to
  maintain something the user doesn't need.
- **C — Keep archiving, make the push robust (`git pull --rebase` + retry).** Rejected: retains
  the branch-litter risk and complexity for no benefit.

## Scope

### In scope

**`briefing/prompt.md`:**
1. Delete Step 5 "Archive to repo" entirely — the `git config` / `git add` / `git commit` /
   `git push origin main` block and the "If push fails for any reason, skip silently and continue" line.
2. Relabel the "Full version — for repo archive" heading (line ~112) to reflect its remaining
   purpose (Notion/email/SMS delivery). The full version is still generated; it is simply never
   written to git.
3. Remove "archive push" from the partial-failure tracking list (lines ~5 and ~171) and delete
   the `archive push failed (403)` example (line ~182).

**`README.md`:**
4. Remove the "It commits a full markdown archive to `briefing/output/`" step from *How it works*.
5. Update the "Run now" verify instruction and the repo-tree diagram to stop referencing
   `briefing/output/`.

**Filesystem:**
6. Delete the `briefing/output/` directory entirely (25 `.md` files + `.gitkeep`). Recoverable
   from git history if ever needed.

### Out of scope (explicitly not in this change)

- Weather and feed-fetching logic — untouched.
- The dead-man's-switch / heartbeat (item #1) — next phase.
- Delivery channel configuration — unchanged.
- Branch-sweep automation — likely unnecessary once branches stop being created; revisit after
  the first post-change run confirms behavior.

## Key facts that make this safe

- **No read-dependency on the archive.** Feed filtering is purely time-based ("items published in
  the last 24 hours"), not based on reading prior output files. Removing the archive breaks nothing.
- **The full version keeps its consumers.** Notion and email delivery (currently disabled in
  `config.json`) render the full version. We keep generating it; we only drop the git write.

## Risks / assumptions

- **Assumption:** "no commits" → "no orphan `claude/*` branch." Evidence supports this
  (successful-push days left no branch), but the Routine harness internals are not documented, so
  this must be confirmed by a live run. If branches still appear, we add the branch-sweep
  automation that was deferred.
- **Consequence to carry forward:** with no git footprint, an external heartbeat (item #1) becomes
  the only way to confirm a run happened at all. This change strengthens the case for doing item #1 next.

## Success criteria

- `grep` of `briefing/prompt.md` and `README.md` for `git push`, `briefing/output`, and `archive`
  returns nothing (outside historical session logs / this spec).
- After one scheduled run: Discord posts as normal, **and** `git fetch` shows no new commit on
  `origin/main` and no new `claude/*` branch on origin.

## Verification

- **Static:** grep the repo as above.
- **Live:** trigger one run via "Run now"; confirm the Discord messages arrive; run
  `git fetch --prune && git branch -r && git log -1 origin/main` and confirm no new branch and no
  new commit.
