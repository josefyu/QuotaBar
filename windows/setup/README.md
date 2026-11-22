# QuotaBar unter Windows einrichten

```
powershell -ExecutionPolicy Bypass -File .\install-quotabar.ps1
```

Das Skript laedt die Release (mit SHA256-Pruefung), installiert eine **neutrale Vorlage**
(`Konto 1-3`), richtet Autostart ein und legt zwei Desktop-Symbole an: `QuotaBar` und
`QuotaBar Login`. Letzteres meldet fehlende Claude-Konten nacheinander an
(pro Konto im Claude-Fenster `/login`, dann `/exit`). Es liest die Konten aus der
installierten `settings.json`, passt sich also an eigene Einstellungen an.

## Eigene Einstellungen

Ordner `meine-einstellungen\` neben `install-quotabar.ps1` anlegen, Inhalt wie
`%APPDATA%\ClaudeCodeUsageMonitor` (`settings.json`, `themes\`, ...). Der Installer nimmt
ihn statt der Vorlage. Der Ordner steht in `.gitignore`.
Anmeldedaten (`.credentials.json`) gehoeren nie in dieses Repo; sie bleiben in den
`.claude*`-Ordnern des jeweiligen Rechners.
