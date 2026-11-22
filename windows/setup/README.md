# QuotaBar unter Windows einrichten

```
irm https://raw.githubusercontent.com/josefyu/QuotaBar/main/windows/setup/install.ps1 | iex
```

Lokal aus einem Klon: `powershell -ExecutionPolicy Bypass -File .\install.ps1`.
Bestimmte Release: vorher `$env:QUOTABAR_TAG = "v2.13.44-quotabar.2"` setzen.

Das Skript laedt die Release (mit SHA256-Pruefung), installiert eine **neutrale Vorlage**
(`Konto 1-3`), richtet Autostart ein und legt zwei Desktop-Symbole an: `QuotaBar` und
`QuotaBar Login`. Letzteres meldet fehlende Claude-Konten nacheinander an
(pro Konto im Claude-Fenster `/login`, dann `/exit`). Es liest die Konten aus der
installierten `settings.json`, passt sich also an eigene Einstellungen an.

## Eigene Einstellungen

Ordner `meine-einstellungen\` (neben `install.ps1` oder direkt in `%USERPROFILE%`, oder per
`$env:QUOTABAR_SETTINGS` angegeben) anlegen, Inhalt wie
`%APPDATA%\ClaudeCodeUsageMonitor` (`settings.json`, `themes\`, ...). Der Installer nimmt
ihn statt der Vorlage. Der Ordner steht in `.gitignore`.
Anmeldedaten (`.credentials.json`) gehoeren nie in dieses Repo; sie bleiben in den
`.claude*`-Ordnern des jeweiligen Rechners.
