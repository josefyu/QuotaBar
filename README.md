![Linux](https://img.shields.io/badge/platform-Linux-green)
![Windows](https://img.shields.io/badge/platform-Windows-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# QuotaBar

> A local quota monitor for AI coding agents.

QuotaBar keeps the usage windows of your authenticated coding agents visible
without a browser tab. The actively maintained Linux tray app shows **Claude
Code** and **Codex CLI** side by side, with live reset countdowns and threshold
alerts. It uses your local CLI credentials directly; there is no backend service
or Python virtual environment.

| Platform | Current scope |
| --- | --- |
| **Linux** | Native AppIndicator tray app for Claude Code and Codex CLI |
| **Windows** | Original upstream taskbar monitor, retained in this repository |

**Repository:** [github.com/josefyu/QuotaBar](https://github.com/josefyu/QuotaBar)

## Linux — Claude Code and Codex CLI

The Linux implementation lives in [`linux/`](linux/) and is the recommended
QuotaBar experience.

![Linux tray monitor](.github/linux-tray.gif)

This image is rendered by the monitor itself: [`linux/tools/render_demo.py`](linux/tools/render_demo.py) uses the same icon code as the tray, so it is not a desktop screenshot.

### What you get

- Separate, matching Claude (`C`) and Codex (`X`) tray indicators
- 5-hour and 7-day quota windows, reset countdowns, and warning notifications
- Manual refresh, configurable polling interval, and optional panel labels
- Automatic local-CLI refresh for expired credentials
- Headless terminal and JSON modes for scripts or SSH sessions

### Requirements

| Required | Optional |
| --- | --- |
| Linux desktop with an AppIndicator-compatible tray | Codex CLI, installed and signed in |
| Python 3 | Desktop notifications (`gir1.2-notify-0.7`) |
| Claude Code, installed and signed in | |

On Debian/Ubuntu, QuotaBar installs `python3-gi`, `python3-gi-cairo`, and an
Ayatana/AppIndicator binding during the one-command setup below.

### Install and run

On a Debian/Ubuntu desktop, the first-time setup and immediate start are one command:

```bash
cd /path/to/QuotaBar && ./linux/install.sh --install-deps --start
```

`--install-deps` installs the required AppIndicator packages through `apt` and
may ask for your sudo password. `--start` launches the tray monitor immediately.
QuotaBar also creates an XDG autostart entry, so it starts automatically at your
next desktop login.

Later starts need only:

```bash
claude-usage-monitor &
```

To check credentials and usage before starting the tray:

```bash
claude-usage-monitor --once
```

The launcher is installed at `~/.local/bin/claude-usage-monitor`. Settings live
in `~/.config/claude-usage-monitor/config.json` (or the equivalent under
`XDG_CONFIG_HOME`).

### Tray icons

Claude and Codex use separate, visually identical tray indicators. Each has two concentric usage rings:

- Outer ring: 5-hour window
- Inner ring: 7-day window
- Centre glyph: `C` for Claude or `X` for Codex

The Codex indicator is shown only when the Codex CLI is signed in. Without Codex credentials, only the two-ring Claude indicator is shown.

Ring colors follow the configured usage thresholds: green below 50%, yellow from 50%, orange from the warning threshold, and red from the critical threshold. If no Claude usage data can be read, the tray shows an error icon.

### Panel labels

The optional text labels next to the icons use this format:

```text
Cl 42% · 68%    Cx 17% · 31%
```

Each pair is the respective 5-hour and 7-day usage. The labels can be disabled from the tray menu entry `Text im Panel`.

### Tray menu

Each Linux tray indicator has its own menu, which shows:

- Its own `5h` and `7d` rows with reset countdowns
- Timestamp of the last successful fetch
- `Jetzt aktualisieren`
- `Aktualisierungsintervall`
- `Text im Panel`
- `Benachrichtigungen`
- `Beenden`

Menu labels are German.

### Terminal modes

The Linux monitor can also run without the tray:

```bash
claude-usage-monitor --once
claude-usage-monitor --once --json
claude-usage-monitor --watch --interval 300
```

### Privacy and data handling

The Linux monitor reads local credentials from `~/.claude/.credentials.json` and, when present, `$CODEX_HOME/auth.json` or `~/.codex/auth.json`.

Network access is limited to Anthropic's Claude usage lookup (including its
Messages API fallback) and ChatGPT's Codex usage endpoint. There is no update
check, telemetry, or backend service in the Linux implementation.

Expired tokens are refreshed by invoking the respective local CLI. The monitor does not write credential files itself.

The only local monitor state is `~/.config/claude-usage-monitor/config.json`, which stores the polling interval, panel-label toggle, and notification toggle. It does not store window position, language, or update-check timestamps.

### How it works

The Linux monitor reads local credentials, queries the provider usage endpoints, renders the tray icon as a PNG in `XDG_RUNTIME_DIR`, and passes that icon to AppIndicator.

Polling runs in a background thread at the configured interval, and the poller wakes early when credential files change or when `Jetzt aktualisieren` is selected.

### Regenerating the demo

```bash
python3 linux/tools/render_demo.py
```

## Attribution

The Windows implementation was originally created by [Craig Constable / CodeZeno](https://github.com/CodeZeno/Claude-Code-Usage-Monitor). This project retains the original MIT license and copyright notice.

The Linux implementation in [`linux/`](linux/) is an independent Linux desktop
adaptation, maintained in [josefyu/QuotaBar](https://github.com/josefyu/QuotaBar)
by [josefyu](https://github.com/josefyu).

## Windows — original upstream implementation

The Windows code and documentation below describe the original Claude Code
Usage Monitor. They are retained for compatibility and attribution; QuotaBar's
Linux tray app is the actively maintained implementation in this repository.

The sections below document the original upstream Windows application. WinGet and release downloads point to [CodeZeno/Claude-Code-Usage-Monitor](https://github.com/CodeZeno/Claude-Code-Usage-Monitor), not this Linux-focused fork.

![Screenshot](.github/animation.gif)

A lightweight Windows taskbar widget for people already using Claude Code, with optional Codex and Google Antigravity usage display.

It sits in your taskbar and shows how much of your Claude Code, Codex, and/or Antigravity usage window you have left, without needing to open the terminal or the provider site.

### What You Get

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

### Who This Is For

This app is for Windows users who already have **Claude Code (CLI or App) installed and signed in**.

Codex support is optional. To show Codex usage, install and sign in to the Codex CLI, then enable Codex from the right-click **Models** menu.

Antigravity support is optional too. To show Antigravity usage, install and sign in to Google Antigravity, then enable the **Antigravity** model from the right-click **Models** menu.

It works best if you want a simple "how close am I to the limit?" display that is always visible.

### Requirements

- Windows 10 or Windows 11
- Claude Code (CLI or App) installed and authenticated
- Optional: Codex CLI installed and authenticated, if you want Codex usage
- Optional: Google Antigravity installed and authenticated, if you want Antigravity usage

If you use Claude Code through WSL, that is supported too. The monitor can read your Claude Code credentials from Windows or from your WSL environment.

### Install

For the original upstream Windows distribution, install the latest version from CodeZeno's WinGet package:

```powershell
winget install CodeZeno.ClaudeCodeUsageMonitor
```

If you prefer not to use WinGet, download the latest upstream `claude-code-usage-monitor.exe` from the [CodeZeno Releases](https://github.com/CodeZeno/Claude-Code-Usage-Monitor/releases) page and run it directly. These Windows release artifacts are not published from this fork.

### Use

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

### Diagnostics

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

### Privacy And Security

This section describes the original upstream Windows app.

What the Windows app reads:

- Your local Claude Code OAuth credentials from `~/.claude/.credentials.json`
- If needed, the same credentials file inside an installed WSL distro
- If Codex is enabled, your local Codex credentials from `$CODEX_HOME/auth.json` or `~/.codex/auth.json`
- If Antigravity is enabled, your local Antigravity OAuth token from Windows Credential Manager target `gemini:antigravity`

What the Windows app sends over the network:

- Requests to Anthropic's Claude endpoints to read your usage and rate-limit information
- Requests to ChatGPT's Codex usage endpoint to read your Codex usage and rate-limit information, if Codex is enabled
- Requests to Google's Cloud Code / Antigravity endpoints to read your Antigravity quota information, if Antigravity is enabled
- Requests to GitHub only if you use the app's update check / self-update feature
- If proxy environment variables such as `HTTPS_PROXY`, `HTTP_PROXY`, or `ALL_PROXY` are set, those outbound requests may use that proxy

What the Windows app stores locally:

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
- Portable installs can update themselves by downloading the latest upstream release
- Proxies should be trusted because proxied usage requests include your OAuth bearer token inside the TLS connection

### How It Works

The Windows monitor:

1. Finds your enabled model login credentials
2. Reads your current usage from Anthropic, ChatGPT, and/or Google's Antigravity endpoints
3. Shows the result directly in the Windows taskbar
4. Keeps the widget aligned with the selected taskbar and tray area
5. Refreshes periodically in the background

If the newer usage endpoint is unavailable, it can fall back to reading the rate-limit headers returned by Claude's Messages API.

## Account Support

QuotaBar works only with accounts that can sign in to the corresponding local
CLI and whose provider exposes usage data through its authenticated endpoint.
Provider plans, limits, and endpoint behaviour can change; QuotaBar does not
add account eligibility beyond Claude Code or Codex CLI themselves.

## Open Source

QuotaBar is licensed under [MIT](LICENSE).

If you want to inspect the behavior or audit the code, everything is in this repository.
