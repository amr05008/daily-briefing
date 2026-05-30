# Pi 5 Always-On Discord Channel Implementation Plan

> **This is a companion setup plan** — work through it phase by phase with Claude Code.

**Goal:** Run a persistent Claude Code session on Raspberry Pi 5 that receives and responds to Discord messages two-way, recreating King Ziti's always-on task/command interface without custom server maintenance.

**Architecture:** Claude Code on Pi 5 runs with the Discord channel plugin enabled inside a tmux session. A systemd service auto-starts the session on boot. You send messages from Discord on any device → Claude receives them, uses local tools (files, scripts, the web), and replies back to Discord.

**Tech Stack:** Claude Code CLI, Discord bot (Discord Developer Portal), discord@claude-plugins-official channel plugin, tmux, systemd, Tailscale (already set up)

**Pi:** Raspberry Pi 5, ARM64 Linux

---

## Phase 1: Install Claude Code on the Pi

### Task 1.1 — SSH into Pi via Tailscale

- [ ] On your Mac, open Terminal
- [ ] SSH into Pi: `ssh pi@<your-pi-tailscale-ip>` (or whatever your Pi's hostname is in Tailscale)
- [ ] Verify you're on the Pi: `uname -m` → should return `aarch64`

### Task 1.2 — Install Node.js

Claude Code requires Node.js 18+. Use nvm for clean version management.

- [ ] Install nvm:
  ```bash
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  ```
- [ ] Reload shell:
  ```bash
  source ~/.bashrc
  ```
- [ ] Install Node 20 LTS:
  ```bash
  nvm install 20
  nvm use 20
  nvm alias default 20
  ```
- [ ] Verify: `node --version` → should show `v20.x.x`

### Task 1.3 — Install Claude Code

- [ ] Install globally:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- [ ] Verify install: `claude --version`

### Task 1.4 — Log in to Claude Code

On a headless Pi, login will print a URL instead of opening a browser.

- [ ] Start login:
  ```bash
  claude
  ```
- [ ] Claude will print a URL like `https://claude.ai/auth/...` — copy it
- [ ] Open that URL in your browser on your **Mac** and complete the login
- [ ] Back on the Pi, the session should authenticate automatically
- [ ] Type `/exit` to close the session for now
- [ ] Verify auth persisted: `claude --print "say hello"` → should return a response

---

## Phase 2: Create the Discord Bot

This is done in the browser on your Mac, not on the Pi.

### Task 2.1 — Create a Discord Application

- [ ] Go to: https://discord.com/developers/applications
- [ ] Click **"New Application"**
- [ ] Name it something like `King Ziti` or `Pi Claude` — this is internal
- [ ] Click **Create**

### Task 2.2 — Create the Bot

- [ ] In the left sidebar, click **"Bot"**
- [ ] Click **"Add Bot"** → confirm
- [ ] Under **"Privileged Gateway Intents"**, enable:
  - **Message Content Intent** ← required for Claude to read your messages
  - **Server Members Intent** (optional but useful)
- [ ] Click **"Save Changes"**
- [ ] Click **"Reset Token"** → copy and save the token somewhere safe (you'll need it in Phase 3)

### Task 2.3 — Invite Bot to Your Server

- [ ] In the left sidebar, click **"OAuth2"** → **"URL Generator"**
- [ ] Under **Scopes**, check: `bot`
- [ ] Under **Bot Permissions**, check:
  - `Send Messages`
  - `Read Message History`
  - `View Channels`
  - `Read Messages/View Channels`
- [ ] Copy the generated URL at the bottom
- [ ] Open that URL in your browser → select your Discord server → Authorize
- [ ] Verify the bot appears in your server's member list (it will show as offline for now)

---

## Phase 3: Install and Configure the Discord Channel Plugin

Back on the Pi (via SSH).

### Task 3.1 — Install the Discord Plugin

- [ ] Start Claude Code on the Pi:
  ```bash
  claude
  ```
- [ ] Inside the session, install the plugin:
  ```
  /plugin install discord@claude-plugins-official
  ```
- [ ] Wait for install to complete, then exit:
  ```
  /exit
  ```

### Task 3.2 — Configure the Bot Token

- [ ] Start Claude Code again:
  ```bash
  claude
  ```
- [ ] Configure the bot token (replace with your actual token from Task 2.2):
  ```
  /discord:configure <YOUR_BOT_TOKEN>
  ```
- [ ] You should get a confirmation. Exit:
  ```
  /exit
  ```

### Task 3.3 — Test the Two-Way Connection

- [ ] Start Claude with the Discord channel enabled:
  ```bash
  claude --channels plugin:discord@claude-plugins-official
  ```
- [ ] Go to your Discord server and send a message in the channel where the bot is present
- [ ] Watch the Pi terminal — Claude should receive the message and respond in Discord
- [ ] Verify the reply appears in Discord
- [ ] If it works: exit with `/exit`
- [ ] **If it doesn't work:** Check that Message Content Intent is enabled (Task 2.2) and the bot has correct permissions in the specific channel

### Task 3.4 — Lock Down Access (Optional but Recommended)

By default, anyone in the server can trigger Claude. Restrict it to yourself:

- [ ] In the Claude session with Discord channel active:
  ```
  /discord:access pair
  ```
  Follow the pairing instructions to link your Discord account.
- [ ] Then set policy:
  ```
  /discord:access policy allowlist
  ```
- [ ] Now only your Discord account can send commands to Claude

---

## Phase 4: Persistent Session with tmux + systemd

This makes the session survive SSH disconnects and auto-start on reboot.

### Task 4.1 — Install tmux

- [ ] On the Pi:
  ```bash
  sudo apt update && sudo apt install tmux -y
  ```
- [ ] Verify: `tmux -V`

### Task 4.2 — Create the Startup Script

- [ ] Create the script:
  ```bash
  mkdir -p ~/claude-channel
  nano ~/claude-channel/start.sh
  ```
- [ ] Paste this content:
  ```bash
  #!/bin/bash
  # Load nvm so claude is available
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

  # Change to home dir
  cd ~

  # Start claude with discord channel
  exec claude --channels plugin:discord@claude-plugins-official
  ```
- [ ] Save and exit (`Ctrl+X`, `Y`, `Enter`)
- [ ] Make executable:
  ```bash
  chmod +x ~/claude-channel/start.sh
  ```
- [ ] Test it manually:
  ```bash
  tmux new-session -d -s claude-channel '~/claude-channel/start.sh'
  ```
- [ ] Verify it's running: `tmux ls` → should show `claude-channel`
- [ ] Attach to check: `tmux attach -t claude-channel`
  - You should see a Claude session running
  - Detach without stopping: `Ctrl+B`, then `D`
- [ ] Send a Discord message to confirm it still works through tmux

### Task 4.3 — Auto-Start on Boot with systemd

- [ ] Create the service file:
  ```bash
  sudo nano /etc/systemd/system/claude-channel.service
  ```
- [ ] Paste this (replace `pi` with your actual Pi username):
  ```ini
  [Unit]
  Description=Claude Code Discord Channel
  After=network-online.target
  Wants=network-online.target

  [Service]
  Type=forking
  User=pi
  ExecStart=/usr/bin/tmux new-session -d -s claude-channel '/home/pi/claude-channel/start.sh'
  ExecStop=/usr/bin/tmux kill-session -t claude-channel
  Restart=on-failure
  RestartSec=30

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] Save and exit
- [ ] Enable and start the service:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable claude-channel
  sudo systemctl start claude-channel
  ```
- [ ] Verify it's running: `sudo systemctl status claude-channel`

### Task 4.4 — Test Reboot

- [ ] Reboot the Pi:
  ```bash
  sudo reboot
  ```
- [ ] Wait ~60 seconds, then SSH back in via Tailscale
- [ ] Check the session is running: `tmux ls`
- [ ] Send a Discord message — Claude should respond
- [ ] **Success:** You now have a persistent, always-on Claude session on your Pi with Discord two-way communication

---

## Phase 5: Connect to scheduled-agents Repo

Get Claude aware of your existing work so Discord commands can trigger your scripts.

### Task 5.1 — Clone scheduled-agents on Pi

- [ ] On the Pi:
  ```bash
  cd ~
  git clone https://github.com/amr05008/scheduled-agents.git
  ```

### Task 5.2 — Add a CLAUDE.md for Pi Context

Give the Pi's Claude session context about what it's running and what it can do.

- [ ] Create `~/CLAUDE.md`:
  ```bash
  nano ~/CLAUDE.md
  ```
- [ ] Add content like:
  ```markdown
  # Pi Claude — Always-On Discord Assistant

  This Claude session runs 24/7 on a Raspberry Pi 5 in Brooklyn.
  It receives commands via Discord and can use local tools.

  ## What's Available
  - ~/scheduled-agents/ — daily briefing bot (weather + RSS → Discord)
  - ~/monthly-finances/ — finance tally scripts (if cloned)

  ## Discord Usage
  - Users: Aaron only (allowlisted)
  - Purpose: task tracking, running scripts, answering questions, research

  ## Notes
  - Always-on session — be conservative with resource-heavy tasks
  - Respond concisely in Discord (messages have length limits)
  ```
- [ ] Save and exit

### Task 5.3 — Restart the Session to Pick Up CLAUDE.md

- [ ] Kill the current session:
  ```bash
  tmux kill-session -t claude-channel
  ```
- [ ] Start it again (systemd will restart it automatically within 30s, or run manually):
  ```bash
  ~/claude-channel/start.sh
  ```
  Or just wait for systemd to restart it.
- [ ] Attach and verify CLAUDE.md is loaded: `tmux attach -t claude-channel`
  - You should see Claude reference the Pi context on startup
  - Detach: `Ctrl+B`, `D`

---

## You're Done

At this point you have:
- Claude Code running persistently on Pi 5
- Discord two-way: you send a message, Claude responds
- Auto-starts on reboot
- Aware of your scheduled-agents repo and can run scripts on command

**Test commands to try from Discord:**
- "what time is it" (simple sanity check)
- "run the briefing script" (tests script access)
- "add 'research swim classes' to my task list" (the King Ziti use case)
- "what's on my task list"

---

## Troubleshooting

**Claude isn't responding in Discord:**
1. Check tmux session is alive: `tmux ls`
2. Check Discord bot is online in your server (green dot)
3. Check Message Content Intent is enabled in Discord Developer Portal
4. Check bot has permission to read/send in that specific channel

**Session dies after a while:**
- Check systemd logs: `sudo journalctl -u claude-channel -n 50`
- May need to extend Claude's session timeout or add a keepalive

**Auth expires:**
- Re-run `claude` and log in again, then restart the service
- Auth tokens should persist in `~/.claude/` — back this up after setup
