# QuotaBar fuer Windows installieren. In PowerShell aus diesem Ordner:
#   powershell -ExecutionPolicy Bypass -File .\install-quotabar.ps1
# Optional: -Tag v2.13.44-quotabar.2   (Standard: neueste Release)
#
# Eigene Einstellungen (echte Kontonamen, Layout): Ordner "meine-einstellungen"
# neben dieses Skript legen (Inhalt wie %APPDATA%\ClaudeCodeUsageMonitor).
# Er hat Vorrang vor der neutralen Vorlage und steht in .gitignore.

param([string]$Tag = "latest")

$ErrorActionPreference = "Stop"
$repo       = "josefyu/QuotaBar"
$exeName    = "claude-code-usage-monitor.exe"
$installDir = Join-Path $env:LOCALAPPDATA "QuotaBar"
$appData    = Join-Path $env:APPDATA "ClaudeCodeUsageMonitor"
$here       = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Release-Exe laden und Pruefsumme kontrollieren
$base = if ($Tag -eq "latest") { "https://github.com/$repo/releases/latest/download" }
        else { "https://github.com/$repo/releases/download/$Tag" }
New-Item -ItemType Directory -Force $installDir | Out-Null
$exe = Join-Path $installDir $exeName
Get-Process claude-code-usage-monitor -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Lade $base/$exeName"
Invoke-WebRequest "$base/$exeName" -OutFile $exe -UseBasicParsing
$shaRaw = (Invoke-WebRequest "$base/$exeName.sha256" -UseBasicParsing).Content
if ($shaRaw -is [byte[]]) { $shaRaw = [Text.Encoding]::ASCII.GetString($shaRaw) }  # PS 5.1 liefert Bytes
$expected = ($shaRaw -split '\s+')[0].Trim().ToLower()
$actual   = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
if ($expected -ne $actual) { throw "SHA256 stimmt nicht: erwartet $expected, erhalten $actual" }
Write-Host "Pruefsumme OK"

# 2. Einstellungen: eigene (meine-einstellungen) oder neutrale Vorlage
$mine = Join-Path $here "meine-einstellungen"
$src  = if (Test-Path $mine) { $mine } else { Join-Path $here "ClaudeCodeUsageMonitor" }
if (Test-Path $src) {
    if (Test-Path $appData) {
        $bak = "$appData.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item $appData $bak -Recurse
        Write-Host "Bisherige Konfiguration gesichert: $bak"
    }
    New-Item -ItemType Directory -Force $appData | Out-Null
    Copy-Item (Join-Path $src "*") $appData -Recurse -Force
    $settings = Join-Path $appData "settings.json"
    # Benutzerpfad in der JSON-Datei (maskierte Backslashes) auf diesen Rechner setzen
    $json = [regex]::Replace((Get-Content $settings -Raw), 'C:\\\\Users\\\\[^\\]+', $HOME.Replace('\', '\\'))
    [IO.File]::WriteAllText($settings, $json)
    Write-Host "Einstellungen installiert aus: $src"
}

# 3. Login-Hilfe, Autostart, Desktop-Symbole
foreach ($f in "QuotaBar-Login.ps1", "QuotaBar-Login.cmd") { Copy-Item (Join-Path $here $f) $installDir -Force }
Set-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run -Name ClaudeCodeUsageMonitor -Value $exe
$desktop = [Environment]::GetFolderPath("Desktop")
$sh = New-Object -ComObject WScript.Shell
$l1 = $sh.CreateShortcut((Join-Path $desktop "QuotaBar.lnk"));       $l1.TargetPath = $exe; $l1.Save()
$l2 = $sh.CreateShortcut((Join-Path $desktop "QuotaBar Login.lnk")); $l2.TargetPath = (Join-Path $installDir "QuotaBar-Login.cmd"); $l2.Save()

Start-Process $exe
Write-Host "`nQuotaBar laeuft: $exe`nKonten-Status:"
& (Join-Path $installDir "QuotaBar-Login.ps1") -Status
Write-Host "`nFehlt ein Konto: Desktop-Symbol 'QuotaBar Login' doppelklicken."
