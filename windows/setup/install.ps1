# QuotaBar fuer Windows installieren.
#
#   irm https://raw.githubusercontent.com/josefyu/QuotaBar/main/windows/setup/install.ps1 | iex
#
# Optionen (vor dem Einzeiler setzen, gelten nur fuer diese PowerShell):
#   $env:QUOTABAR_TAG = "v2.13.44-quotabar.2"   # bestimmte Release statt der neuesten
#   $env:QUOTABAR_SETTINGS = "D:\pfad\ordner"   # eigene Einstellungen (siehe README)
# Lokal aus einem Klon: powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# Eigene Einstellungen haben Vorrang vor der neutralen Vorlage. Gesucht wird in:
# $env:QUOTABAR_SETTINGS, "meine-einstellungen" neben dem Skript, $HOME\meine-einstellungen.
# Diese Ordner gehoeren nie ins Repo.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Fortschrittsanzeige macht Downloads in PS 5.1 langsam
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo       = "josefyu/QuotaBar"
$exeName    = "claude-code-usage-monitor.exe"
$tag        = if ($env:QUOTABAR_TAG) { $env:QUOTABAR_TAG } else { "latest" }
$installDir = Join-Path $env:LOCALAPPDATA "QuotaBar"
$appData    = Join-Path $env:APPDATA "ClaudeCodeUsageMonitor"
$tmp        = Join-Path $env:TEMP "quotabar-install"

# 0. Quelle der Setup-Dateien: lokaler Klon oder ZIP von GitHub (bei irm | iex)
if ($MyInvocation.MyCommand.Path) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $ref = if ($tag -eq "latest") { "heads/main" } else { "tags/$tag" }
    Write-Host "Lade Setup-Dateien ($ref)"
    Invoke-WebRequest "https://github.com/$repo/archive/refs/$ref.zip" -OutFile "$tmp\src.zip" -UseBasicParsing
    Expand-Archive "$tmp\src.zip" "$tmp\src" -Force
    $here = (Get-ChildItem "$tmp\src" -Directory | Select-Object -First 1).FullName + "\windows\setup"
}

# 1. Release-Exe laden und Pruefsumme kontrollieren
$base = if ($tag -eq "latest") { "https://github.com/$repo/releases/latest/download" }
        else { "https://github.com/$repo/releases/download/$tag" }
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

# 2. Einstellungen: eigene oder neutrale Vorlage
$src = @($env:QUOTABAR_SETTINGS, (Join-Path $here "meine-einstellungen"), (Join-Path $HOME "meine-einstellungen")) |
    Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $src) { $src = Join-Path $here "ClaudeCodeUsageMonitor" }
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
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
