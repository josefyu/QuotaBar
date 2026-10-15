# QuotaBar setup for a second Windows machine (e.g. Zenbook).
# Run in PowerShell from this folder:
#   powershell -ExecutionPolicy Bypass -File .\install-quotabar.ps1
# Optional: -Tag v2.13.44-quotabar.2   (default: latest release)
#
# The bundled settings use neutral account labels ("Konto 1-3") and config
# folders (~\.claude-konto1-3). Sign in per account with
#   $env:CLAUDE_CONFIG_DIR="$HOME\.claude-konto1"; claude
# or point config_dir in settings.json at your existing folders.

param([string]$Tag = "latest")

$ErrorActionPreference = "Stop"
$repo     = "josefyu/QuotaBar"
$exeName  = "claude-code-usage-monitor.exe"
$installDir = Join-Path $env:LOCALAPPDATA "QuotaBar"
$appData  = Join-Path $env:APPDATA "ClaudeCodeUsageMonitor"
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Download release exe + checksum
$base = if ($Tag -eq "latest") { "https://github.com/$repo/releases/latest/download" }
        else { "https://github.com/$repo/releases/download/$Tag" }
New-Item -ItemType Directory -Force $installDir | Out-Null
$exe = Join-Path $installDir $exeName
Get-Process claude-code-usage-monitor -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Downloading $base/$exeName"
Invoke-WebRequest "$base/$exeName" -OutFile $exe -UseBasicParsing
$expected = ((Invoke-WebRequest "$base/$exeName.sha256" -UseBasicParsing).Content -split '\s+')[0].Trim().ToLower()
$actual = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
if ($expected -ne $actual) { throw "SHA256 mismatch: expected $expected, got $actual" }
Write-Host "Checksum OK"

# 2. Copy settings + themes from the Fujitsu, rewriting the user path
$src = Join-Path $here "ClaudeCodeUsageMonitor"
if (Test-Path $src) {
    if (Test-Path $appData) {
        $bak = "$appData.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item $appData $bak -Recurse
        Write-Host "Existing config backed up to $bak"
    }
    New-Item -ItemType Directory -Force $appData | Out-Null
    Copy-Item (Join-Path $src "*") $appData -Recurse -Force
    $settings = Join-Path $appData "settings.json"
    $json = Get-Content $settings -Raw
    $json = $json.Replace('C:\\Users\\fujitsu', ($HOME -replace '\\', '\\'))
    [IO.File]::WriteAllText($settings, $json)
    Write-Host "Settings and themes installed"

    # Warn about account folders that don't exist on this machine yet
    $cfg = $json | ConvertFrom-Json
    foreach ($p in $cfg.accounts.claude.profiles) {
        if ($p.config_dir -and -not (Test-Path $p.config_dir)) {
            Write-Warning "Account '$($p.name)': $($p.config_dir) missing - sign in with CLAUDE_CONFIG_DIR=$($p.config_dir) claude"
        }
    }
}

# 3. Autostart + desktop shortcut
Set-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run -Name ClaudeCodeUsageMonitor -Value $exe
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "QuotaBar.lnk"))
$lnk.TargetPath = $exe
$lnk.Save()

Start-Process $exe
Write-Host "QuotaBar running from $exe"
