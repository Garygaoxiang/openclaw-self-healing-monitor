# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of utility scripts and a Chrome extension that together form an automation and monitoring solution for **OpenClaw** — a browser automation gateway. The system allows OpenClaw Gateway to control Chrome via CDP (Chrome DevTools Protocol).

## Architecture

```
Chrome Browser (port 9222/9223)
    ↓ CDP
openclaw-browser-relay-extension  (Chrome MV3 extension)
    ↓ WebSocket (port 18792)
OpenClaw Gateway Relay Server
    ↓ HTTP (port 18789)
OpenClaw Gateway
    ↑
clawdbot-monitor  (health checks, auto-restart, self-healing)
    └→ openclaw doctor [--fix]  →  Claude Code fallback  →  Telegram alerts
```

## Key Components

### `openclaw-browser-relay-extension/`
Chrome Manifest V3 extension. **background.js** is the main service worker managing:
- WebSocket connection to relay server (reconnect with exponential backoff via `background-utils.js`)
- Chrome debugger attach/detach and CDP forwarding
- State persistence across service worker restarts via `chrome.storage.local`
- Keepalive via `chrome.alarms` every 30s

Token authentication: `background-utils.js:deriveRelayToken()` uses HMAC-SHA256 to derive a relay token from the gateway token.

### `clawdbot-monitor/`
Two monitoring implementations:
- **clawdbot-monitor.sh** — Bash, simple health check + auto-restart (port 18789, 30s interval)
- **clawdbot-monitor-self-healing.py** — Python, advanced self-healing with fallback chain:
  1. Auto-restart Gateway
  2. Run `openclaw doctor --fix`
  3. Invoke Claude Code (via WSL) for intelligent fix
  4. Open interactive repair window
  5. Send Telegram notification

### `chrome9222/`, `chrome9223/`
Batch scripts to launch isolated Chrome instances with `--remote-debugging-port=9222/9223`, auto-loading the relay extension from `F:\Scripts\openclaw-browser-relay-extension`.

### `claude code script/claude-code-multi-key.ps1`
Interactive PowerShell menu to switch between 5 preconfigured Claude API endpoints (MiniMax, Moonshot, ZhipuAI, ZhihuiAPI, Custom).

## Common Commands

```bash
# Monitor — Bash (simple)
./clawdbot-monitor/clawdbot-monitor.sh start|stop|restart|status

# Monitor — Python (self-healing)
python3 ./clawdbot-monitor/clawdbot-monitor-self-healing.py --daemon
python3 ./clawdbot-monitor/clawdbot-monitor-self-healing.py --status
python3 ./clawdbot-monitor/clawdbot-monitor-self-healing.py --fix

# Backup / restore OpenClaw config
./backup-openclaw.sh [output_dir]
./restore-openclaw.sh <backup_file.tar.gz>

# Launch Chrome debug instance
./chrome9222/chrome9222.bat

# Quick Claude launch with custom API endpoint
./claude-fast.sh "your prompt"
```

## Configuration

| Item | Location | Default |
|------|----------|---------|
| Extension relay port | `chrome.storage.local` → `relayPort` | 18792 |
| Extension gateway token | `chrome.storage.local` → `gatewayToken` | — |
| Monitor gateway port | `clawdbot-monitor-self-healing.py` config dict | 18789 |
| Monitor check interval | same | 30s |
| Chrome debug ports | same | 9222, 9223 |
| Extension path (monitor) | same | `F:\Scripts\openclaw-browser-relay-extension` |
| Monitor log | — | `~/.clawdbot/monitor.log` |

Environment variables used: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`.

## Platform Notes

- Scripts run on **Windows 11** with **WSL** for Bash execution. The Python monitor includes WSL path translation and Windows encoding fixes (`sys.stdout` reconfigured for UTF-8).
- Extension options UI (`options.html` / `options.js`) includes a relay connectivity validator before saving settings.
