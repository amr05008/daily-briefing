---
date: 2026-04-12
summary: Plan created for always-on Claude Code session on Pi 5 with two-way Discord via channels plugin
tags: [raspberry-pi, discord, claude-channels, scheduled-agents]
---

## Summary

Designed a plan to run a persistent Claude Code session on Raspberry Pi 5 that enables two-way Discord messaging — replacing the King Ziti / OpenClaw setup with Claude Code's native Discord channels plugin. The session auto-starts on boot via tmux + systemd and is SSH-accessible via Tailscale. Two-way Discord is the primary goal: send a message from Discord on any device, Claude responds.

## Status

**Not started.** Plan written, execution scheduled for tonight (2026-04-12 evening).

## Plan Location

`docs/plans/2026-04-12-pi-discord-channel.md`

## Context for Resuming

- Pi 5 is ARM64 Linux with Tailscale already configured
- Discord channels is a research preview feature in Claude Code — requires `claude.ai` login (not API key)
- Headless Pi login: `claude` will print a URL, open it on Mac browser to authenticate
- Two-way Discord works via `claude --channels plugin:discord@claude-plugins-official`
- King Ziti reference: prior always-on OpenClaw agent on this Pi that handled Discord task lists, swim class research, email reports. Required hundreds of hours of maintenance. This replaces it.
- scheduled-agents repo already exists with daily briefing (weather + RSS → Discord)

## Changes

No code changes yet — plan only.

## How to Resume

Open `docs/plans/2026-04-12-pi-discord-channel.md` and tell Claude:

> "I'm ready to work through the Pi Discord channel setup plan. The plan is at docs/plans/2026-04-12-pi-discord-channel.md — let's start at Phase 1."
