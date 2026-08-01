![Windows](https://img.shields.io/badge/platform-Windows-blue)
![Linux](https://img.shields.io/badge/platform-Linux-green)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Claude Code Usage Monitor

This repository contains the original Windows taskbar monitor and a Linux system-tray implementation. Both show the current Claude Code usage windows; the Linux monitor can also show Codex usage when the Codex CLI is signed in.

**Source:** [github.com/josefyu/QuotaBar](https://github.com/josefyu/QuotaBar)

## Linux

The Linux implementation lives in [`linux/`](linux/) and is a native Python/Gtk/AppIndicator tray application. It reads the same local Claude and optional Codex credentials as the upstream project and queries the respective provider usage endpoints. It does not need a web service or a Python virtual environment.

### Requirements

- A Linux desktop with an AppIndicator-compatible tray (for example GNOME with AppIndicator support)
- Python 3
- Claude Code installed and authenticated
- Optional: Codex CLI installed and authenticated
- Debian/Ubuntu packages: `python3-gi`, `python3-gi-cairo`, and `gir1.2-ayatanaappindicator3-0.1`

### Install and run

```bash
cd linux
./install.sh
claude-usage-monitor --once
claude-usage-monitor &
```

`install.sh` creates a user-local launcher at `~/.local/bin/claude-usage-monitor` and an XDG autostart entry. It checks for missing system dependencies before making changes.

Terminal modes are also available:

```bash
claude-usage-monitor --once
claude-usage-monitor --once --json
claude-usage-monitor --watch --interval 300
```

The Linux configuration is stored at `~/.config/claude-usage-monitor/config.json` (or the equivalent under `XDG_CONFIG_HOME`).

### Linux features

- Claude Code 5-hour and 7-day windows with live reset countdowns
- Optional Codex usage windows
- Status icon with usage thresholds and optional desktop notifications
- Tray controls for manual refresh, polling interval, panel label, notifications, and quit
- Automatic refresh of expired local Claude/Codex credentials through their respective CLIs

## Attribution

The Windows implementation was originally created by [Craig Constable / CodeZeno](https://github.com/CodeZeno/Claude-Code-Usage-Monitor). This project retains the original MIT license and copyright notice.

The Linux implementation in [`linux/`](linux/) was added as an independent adaptation for Linux desktop use. It is maintained in [josefyu/QuotaBar](https://github.com/josefyu/QuotaBar) by [josefyu](https://github.com/josefyu), with implementation assistance from Claude Code.

## Windows

The sections below document the original Windows application.

![Screenshot](.github/animation.gif)

A lightweight Windows taskbar widget for people already using Claude Code, with optional Codex and Google Antigravity usage display.

It sits in your taskbar and shows how much of your Claude Code, Codex, and/or Antigravity usage window you have left, without needing to open the terminal or the provider site.

## What You Get

- A **5h** bar for your current 5-hour Claude usage window
- A **7d** bar for your current 7-day window
- Optional Codex usage bars alongside Claude Code
- Optional Antigravity model usage bars for Google's 5-hour and weekly Gemini quota windows
- A live countdown until each limit resets
- A small native widget that lives directly in the Windows taskbar
- System tray icon badges showing your enabled model usage percentage
- Left-click the tray icon to toggle the taskbar widget on or off
- Right-click options for refresh, displayed models, update frequency, language, startup, widget visibility, and updates
- Multi-monitor taskbar placement, so the widget can live on the taskbar for the screen you prefer

## Who This Is For

This app is for Windows users who already have **Claude Code (CLI or App) installed and signed in**.

Codex support is optional. To show Codex usage, install and sign in to the Codex CLI, then enable Codex from the right-click **Models** menu.

Antigravity support is optional too. To show Antigravity usage, install and sign in to Google Antigravity, then enable the **Antigravity** model from the right-click **Models** menu.

It works best if you want a simple "how close am I to the limit?" display that is always visible.

## Requirements

- Windows 10 or Windows 11
- Claude Code (CLI or App) installed and authenticated
- Optional: Codex CLI installed and authenticated, if you want Codex usage
- Optional: Google Antigravity installed and authenticated, if you want Antigravity usage

If you use Claude Code through WSL, that is supported too. The monitor can read your Claude Code credentials from Windows or from your WSL environment.

## Install

For the original Windows distribution, install the latest upstream version from WinGet:

```powershell
winget install CodeZeno.ClaudeCodeUsageMonitor
```

If you prefer not to use WinGet, download the latest upstream `claude-code-usage-monitor.exe` from the [CodeZeno Releases](https://github.com/CodeZeno/Claude-Code-Usage-Monitor/releases) page and run it directly.

## Use

After installing with WinGet, run:

```powershell
claude-code-usage-monitor
```

Once running, it will appear in your taskbar and as one or more tray icons in the notification area.

- Drag the left divider to move the taskbar widget
- On multi-monitor setups, drag the widget onto another Windows taskbar to move it to that screen
- Right-click the taskbar widget or tray icon for refresh, displayed models, update frequency, Start with Windows, reset position, language, updates, and exit
- Left-click the tray icon to toggle the taskbar widget on or off
- Enable `Start with Windows` from the right-click menu if you want it to launch automatically when you sign in

### Models

Use the right-click **Models** menu to choose what the widget displays:

- **Claude Code** is enabled by default
- **Codex** can be enabled alongside Claude Code or shown by itself
- **Antigravity** can be enabled alongside the other providers or shown by itself as its own model column

When multiple models are shown, each model has its own usage bar and matching usage text color. Antigravity prefers Google's Gemini quota summary when available and falls back to model quota data when needed.

### System Tray Icon

The tray icon shows your current 5-hour usage as a percentage badge.

If multiple providers are enabled, the app shows one tray icon per provider. If only one model is enabled, it shows one tray icon.

The Claude Code tray icon uses the same warm usage colors as the Claude bar. The Codex tray icon uses a black and white badge style. The Antigravity tray icon uses a blue badge style.

Hovering over a tray icon shows the usage values for that model.

## Diagnostics

If you need to troubleshoot startup or visibility issues, run:

```powershell
claude-code-usage-monitor --diagnose
```

This writes a log file to:

```text
%TEMP%\claude-code-usage-monitor.log
```

Settings are saved to:

```text
%APPDATA%\ClaudeCodeUsageMonitor\settings.json
```

## Account Support

This app works with the same account types that Claude Code itself supports.

As of **March 19, 2026**, Anthropic's Claude Code setup documentation says:

- **Supported:** Pro, Max, Teams, Enterprise, and Console accounts
- **Not supported:** the free Claude.ai plan

If Anthropic changes Claude Code availability in the future, this app should follow whatever Claude Code supports, as long as the usage data remains exposed through the same authenticated endpoints.

## Privacy And Security

This project is **open source**, so you can inspect exactly what it does.

What the app reads:

- Your local Claude Code OAuth credentials from `~/.claude/.credentials.json`
- If needed, the same credentials file inside an installed WSL distro
- If Codex is enabled, your local Codex credentials from `$CODEX_HOME/auth.json` or `~/.codex/auth.json`
- If Antigravity is enabled, your local Antigravity OAuth token from Windows Credential Manager target `gemini:antigravity`

What the app sends over the network:

- Requests to Anthropic's Claude endpoints to read your usage and rate-limit information
- Requests to ChatGPT's Codex usage endpoint to read your Codex usage and rate-limit information, if Codex is enabled
- Requests to Google's Cloud Code / Antigravity endpoints to read your Antigravity quota information, if Antigravity is enabled
- Requests to GitHub only if you use the app's update check / self-update feature
- If proxy environment variables such as `HTTPS_PROXY`, `HTTP_PROXY`, or `ALL_PROXY` are set, those outbound requests may use that proxy

What the app stores locally:

- Widget position
- Selected taskbar / screen
- Widget visibility
- Polling frequency
- Language preference
- Last update check time
- Displayed model preferences

What it does **not** do:

- It does not send your credentials to any other server
- It does not use a separate backend service
- It does not collect analytics or telemetry
- It does not upload your project files
- It does not directly edit your Codex credentials file

Notes:

- If your Claude Code token is expired, the app may ask the local Claude CLI to refresh it in the background
- If your Codex token is expired, the app may ask the local Codex CLI to refresh it in the background. The monitor does not write `auth.json` itself; any credential update is handled by the Codex CLI.
- If your Antigravity token is expired, open Antigravity and sign in again. The monitor does not write Windows Credential Manager entries itself.
- Portable installs can update themselves by downloading the latest release from this repository
- Proxies should be trusted because proxied usage requests include your OAuth bearer token inside the TLS connection

## How It Works

The monitor:

1. Finds your enabled model login credentials
2. Reads your current usage from Anthropic, ChatGPT, and/or Google's Antigravity endpoints
3. Shows the result directly in the Windows taskbar
4. Keeps the widget aligned with the selected taskbar and tray area
5. Refreshes periodically in the background

If the newer usage endpoint is unavailable, it can fall back to reading the rate-limit headers returned by Claude's Messages API.

## Open Source

This project is licensed under MIT.

If you want to inspect the behavior or audit the code, everything is in this repository.
