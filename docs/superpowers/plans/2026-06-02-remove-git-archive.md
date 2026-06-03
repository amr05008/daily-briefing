# Remove Git Archiving from Briefing Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the scheduled briefing agent from writing artifacts to git, eliminating the silent push failures and orphan-branch litter, while leaving Discord delivery and full-version generation intact.

**Architecture:** This is a documentation/prompt change, not code. The agent's behavior lives in `briefing/prompt.md` (the instructions the scheduled Routine follows). We delete the "Archive to repo" step and its references, clean the README, delete the now-unused `briefing/output/` directory, then verify with a grep sweep and a live end-to-end run that posts to Discord.

**Tech Stack:** Markdown prompt files, git. No build, no test framework — verification is grep (static) + a live Routine run (behavioral).

**Spec:** `docs/superpowers/specs/2026-06-02-remove-git-archive-design.md`

---

### Task 1: Remove the archive step and references from `briefing/prompt.md`

**Files:**
- Modify: `briefing/prompt.md`

After removing Step 5 ("Archive to repo"), the remaining steps renumber: "Deliver to Discord" 6→5, "Alert on partial failure" 7→6. References to "step 7" must follow.

- [ ] **Step 1: Remove "archive push failed" from the partial-failure tracking line and fix the step reference**

Replace (line ~5):
```
**As you work, track any partial failures** (weather fetch failed, a feed fetched but returned 5xx, archive push failed, Discord post failed). You'll summarize these in step 7 as an alert post to `DISCORD_ALERT_WEBHOOK_URL` so silent degradation becomes visible.
```
with:
```
**As you work, track any partial failures** (weather fetch failed, a feed fetched but returned 5xx, Discord post failed). You'll summarize these in step 6 as an alert post to `DISCORD_ALERT_WEBHOOK_URL` so silent degradation becomes visible.
```

- [ ] **Step 2: Relabel the "Full version" heading (it no longer feeds a repo archive)**

Replace (line ~112):
```
#### Full version — for repo archive
```
with:
```
#### Full version — for Notion/email/SMS delivery
```

- [ ] **Step 3: Delete the entire "5. Archive to repo" section**

Remove this whole block (lines ~125–136, including the trailing blank line before "### 6. Deliver to Discord"):
```
### 5. Archive to repo

Write the full version to `briefing/output/YYYY-MM-DD.md`.
```bash
git config user.email "briefing-agent@scheduled"
git config user.name "Briefing Agent"
git add briefing/output/YYYY-MM-DD.md
git commit -m "briefing: YYYY-MM-DD"
git push origin main
```
If push fails for any reason, skip silently and continue.

```

- [ ] **Step 4: Renumber "Deliver to Discord" from 6 to 5**

Replace:
```
### 6. Deliver to Discord
```
with:
```
### 5. Deliver to Discord
```

- [ ] **Step 5: Renumber "Alert on partial failure" from 7 to 6**

Replace:
```
### 7. Alert on partial failure (only if anything went wrong)
```
with:
```
### 6. Alert on partial failure (only if anything went wrong)
```

- [ ] **Step 6: Remove "archive push" from the alert step's failure list**

Replace (line ~171):
```
If anything failed (weather geocoding/fetch, feed fetch, archive push, Discord post, etc.), POST a one-line status to `$DISCORD_ALERT_WEBHOOK_URL`. Use Python stdlib (not `requests`, which is not pre-installed) to JSON-encode the body, then curl:
```
with:
```
If anything failed (weather geocoding/fetch, feed fetch, Discord post, etc.), POST a one-line status to `$DISCORD_ALERT_WEBHOOK_URL`. Use Python stdlib (not `requests`, which is not pre-installed) to JSON-encode the body, then curl:
```

- [ ] **Step 7: Delete the "archive push failed" alert example**

Remove this bullet (line ~182):
```
- `⚠️ Briefing 2026-05-26 partial: archive push failed (403)`
```

- [ ] **Step 8: Verify prompt.md is clean of archive/git-push references**

Run:
```bash
cd /Users/aaronroy/repos/daily-briefing
grep -niE 'git push|git commit|git add|briefing/output|archive|repo archive|step 7' briefing/prompt.md
```
Expected: no output (empty). If any line prints, fix it before committing.

- [ ] **Step 9: Verify step numbering is sequential 1–6**

Run:
```bash
grep -nE '^### [0-9]+\.' /Users/aaronroy/repos/daily-briefing/briefing/prompt.md
```
Expected: headings numbered 1,2,3,4,5,6 with no gaps and no duplicate numbers. "Deliver to Discord" is 5, "Alert on partial failure" is 6.

- [ ] **Step 10: Commit**

```bash
cd /Users/aaronroy/repos/daily-briefing
git add briefing/prompt.md
git commit -m "$(cat <<'EOF'
briefing: remove git archive step from agent prompt

Agent no longer commits/pushes daily output. Deletes Step 5, renumbers
remaining steps, and drops archive references from the failure tracking.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Clean archive references from `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Remove the archive step from "How it works"**

Remove this line (line ~61):
```
7. It commits a full markdown archive to `briefing/output/`
```
The list now ends at item 6 ("It posts to Discord (or other configured channels)").

- [ ] **Step 2: Fix the "Run now" verify instruction**

Replace (line ~146):
```
Hit "Run now" from [claude.ai/code/scheduled](https://claude.ai/code/scheduled). The agent takes 1–2 minutes to run. Check Discord and `briefing/output/` in your repo to verify.
```
with:
```
Hit "Run now" from [claude.ai/code/scheduled](https://claude.ai/code/scheduled). The agent takes 1–2 minutes to run. Check Discord to verify.
```

- [ ] **Step 3: Remove the `output/` entry from the repo-structure tree**

Remove these two lines (lines ~204–205):
```
  output/
    YYYY-MM-DD.md    ← daily archive committed by the agent
```
The tree now ends at the `config.json` line.

- [ ] **Step 4: Verify README is clean**

Run:
```bash
grep -niE 'briefing/output|markdown archive|daily archive' /Users/aaronroy/repos/daily-briefing/README.md
```
Expected: no output (empty).

- [ ] **Step 5: Commit**

```bash
cd /Users/aaronroy/repos/daily-briefing
git add README.md
git commit -m "$(cat <<'EOF'
readme: drop references to the git output archive

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Delete the `briefing/output/` directory

**Files:**
- Delete: `briefing/output/` (25 `.md` files + `.gitkeep`)

- [ ] **Step 1: Confirm what will be removed**

Run:
```bash
cd /Users/aaronroy/repos/daily-briefing
git ls-files briefing/output/ | wc -l
git ls-files briefing/output/ | sed -n '1p;$p'
```
Expected: a count of 26 (25 dated `.md` files + `.gitkeep`), first/last entries shown. These remain recoverable from git history after deletion.

- [ ] **Step 2: Remove the directory from git and disk**

```bash
cd /Users/aaronroy/repos/daily-briefing
git rm -r briefing/output/
```

- [ ] **Step 3: Verify it's gone**

Run:
```bash
ls /Users/aaronroy/repos/daily-briefing/briefing/output 2>&1
git -C /Users/aaronroy/repos/daily-briefing status --short
```
Expected: `ls` reports "No such file or directory"; `git status` shows the deletions staged.

- [ ] **Step 4: Commit**

```bash
cd /Users/aaronroy/repos/daily-briefing
git commit -m "$(cat <<'EOF'
briefing: delete output archive directory

Recoverable from git history if ever needed.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Full-repo static verification

**Files:** none (verification only)

- [ ] **Step 1: Sweep the whole repo for lingering archive/push references**

Run:
```bash
cd /Users/aaronroy/repos/daily-briefing
grep -rniE 'git push|briefing/output|markdown archive|repo archive|daily archive' \
  --include='*.md' --include='*.json' . \
  | grep -v 'docs/superpowers/'
```
Expected: no output. (Matches inside `docs/superpowers/` — the spec and this plan — are expected and excluded; they document the change.)

- [ ] **Step 2: Confirm working tree is clean and all changes committed**

Run:
```bash
git -C /Users/aaronroy/repos/daily-briefing status --short
```
Expected: no output (clean tree).

---

### Task 5: Live test run — confirm Discord delivery and no git footprint (REQUIRED)

**Files:** none (behavioral verification)

This task is mandatory per the spec. Choose Path A or Path B with the user.

- [ ] **Step 1: Record the current git baseline (to detect any footprint the run leaves)**

Run:
```bash
cd /Users/aaronroy/repos/daily-briefing
git fetch --prune
git log -1 --format='%H %s' origin/main
git branch -r | grep 'claude/' || echo "no claude/* branches"
```
Note the `origin/main` HEAD hash and that there are no `claude/*` branches.

- [ ] **Step 2: Execute one briefing run**

**Path A (preferred) — scheduled Routine:** Ask the user to hit "Run now" at
[claude.ai/code/scheduled](https://claude.ai/code/scheduled). Wait 1–2 minutes for it to finish.

**Path B — local run:** Ask the user for the Discord webhook URL, then run the agent locally:
```bash
cd /Users/aaronroy/repos/daily-briefing
export DISCORD_WEBHOOK_URL='<webhook-url-from-user>'
# Then follow briefing/prompt.md end-to-end: read config.json + user-context.md,
# fetch weather + feeds, compile the two messages, and POST each to $DISCORD_WEBHOOK_URL.
```
Note: Path B exercises delivery but NOT the Routine harness, so the branch/commit check in
Step 4 is only conclusive for Path A (or a later scheduled run).

- [ ] **Step 3: Confirm Discord delivery**

Check the Discord channel. Expected: two messages arrived — Message 1 (weather, with current
conditions / forecast / activity outlook) and Message 2 (feeds, one section per source or
"No new posts today"). Both render correctly and are under the 2000-char limit. Confirm with the user.

- [ ] **Step 4: Confirm no git footprint was left**

Run:
```bash
cd /Users/aaronroy/repos/daily-briefing
git fetch --prune
git log -1 --format='%H %s' origin/main
git branch -r | grep 'claude/' || echo "no claude/* branches"
```
Expected: `origin/main` HEAD is the SAME hash as Step 1 (no new `briefing:` commit), and no new
`claude/*` branch appeared. If a `claude/*` branch DID appear, the deferred branch-sweep
automation is needed — note it for follow-up (item from the original plan) rather than treating
this as a failure of the archive removal.

- [ ] **Step 5: Report results to the user**

Summarize: Discord delivery confirmed (yes/no), git footprint left (none / branch appeared).
This closes out item #2. If everything is clean, the natural next step is item #1 (heartbeat /
dead-man's-switch), since with no git footprint an external heartbeat is now the only signal that
a run happened.

---

## Notes

- No code, no tests, no build — verification is grep + a live run.
- The full-version generation stays in the prompt; it feeds Notion/email/SMS delivery when those
  channels are enabled in `config.json` (all currently disabled).
- The branch-sweep automation from the broader reliability plan is intentionally NOT built here.
  Task 5 Step 4 determines whether it's still needed.
