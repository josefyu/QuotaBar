# Zeigt den Login-Status der in QuotaBar eingetragenen Claude-Konten und meldet
# fehlende nacheinander an. Die Konten stammen aus der installierten settings.json.
# Aufruf: powershell -ExecutionPolicy Bypass -File QuotaBar-Login.ps1 [-Status] [-Neu "Konto 1"]
param([switch]$Status, [string]$Neu)

$settings = Join-Path $env:APPDATA "ClaudeCodeUsageMonitor\settings.json"
if (-not (Test-Path $settings)) { Write-Host "Keine QuotaBar-Einstellungen gefunden: $settings"; return }
$cfg = Get-Content $settings -Raw | ConvertFrom-Json
$konten = @($cfg.accounts.claude.profiles | Where-Object { $_.enabled })

function Get-Dir($p)   { if ($p.config_dir) { $p.config_dir } else { Join-Path $HOME ".claude" } }
function Test-Login($dir) {
    $f = Join-Path $dir ".credentials.json"
    if (-not (Test-Path $f)) { return "fehlt" }
    try { $o = (Get-Content $f -Raw | ConvertFrom-Json).claudeAiOauth } catch { return "defekt" }
    if (-not $o.refreshToken) { return "kein refresh" }
    return "ok"
}

$offen = @()
foreach ($k in $konten) {
    $s = Test-Login (Get-Dir $k)
    "{0,-20} {1}" -f $k.name, $s
    if ($s -ne "ok" -or $k.name -eq $Neu) { $offen += $k }
}
if (-not $offen) { "Alle Konten angemeldet."; return }
if ($Status) { return }

foreach ($k in $offen) {
    "`n>> $($k.name) anmelden: im Claude-Fenster /login tippen, im Browser bestaetigen, dann /exit."
    $env:CLAUDE_CONFIG_DIR = Get-Dir $k
    & claude
}
Remove-Item Env:CLAUDE_CONFIG_DIR -ErrorAction SilentlyContinue
"`nFertig. QuotaBar neu starten (Desktop-Symbol 'QuotaBar')."
