# Separates Codex-Tray-Icon mit 5h- und 7d-Ring

**Datum:** 2026-08-04
**Bereich:** `linux/claude_usage_monitor`

## Problem

Der Linux-Tray-Monitor zeigt heute ein einziges Icon mit drei konzentrischen
Ringen: Claude 5h, Claude 7d und — nur wenn die Codex-CLI eingeloggt ist —
Codex 5h. Das Codex-7d-Fenster erscheint ausschließlich als Menüzeile, nicht als
Ring. Codex teilt sich außerdem Icon, Menü und Panel-Text mit Claude, obwohl es
eine eigenständige Quelle mit eigenen Limits ist.

## Ziel

Codex bekommt ein eigenes Tray-Icon mit eigenen zwei Ringen (5h außen, 7d innen)
und eigenem Menü. Das Claude-Icon zeigt wieder genau seine zwei Fenster.

## Entscheidungen

| Frage | Entscheidung |
|---|---|
| Trennung | Zweiter AppIndicator neben dem Claude-Icon |
| Codex nicht eingeloggt / Fehler | Indicator dynamisch ein- und ausblenden (`ACTIVE`/`PASSIVE`) |
| Codex-Menü | Volles Menü wie Claude; Einstellungen bleiben gemeinsam |
| Benachrichtigungen | Auch für Codex 5h und 7d, gleiche Schwellen |
| Icon-Unterscheidung | Ein Buchstabe im freien Icon-Kern: `C` = Claude, `X` = Codex |
| Panel-Text | Kürzel für beide Quellen: `Cl 80% · 40%` und `Cx 20% · 12%` |

## Architektur

Eine gemeinsame Indicator-Klasse, die zweimal instanziiert wird, plus ein
Koordinator, der Config, Poller und Benachrichtigungen besitzt. `tray.py` (heute
345 Zeilen) wird dabei aufgeteilt.

### `icon.py` — generisches Ring-Rendering

`RingSpec(radius, width)` als Dataclass ersetzt die bisherigen Dicts.

```python
OUTER = RingSpec(radius=26.0, width=6.0)   # 5h-Fenster
INNER = RingSpec(radius=18.0, width=6.0)   # 7d-Fenster

def render_rings(path, pairs: Sequence[tuple[RingSpec, float | None]], glyph: str) -> Path
def render_error(path, glyph: str) -> Path
```

`None` als Prozentwert zeichnet nur den Track, keinen Füllbogen — das deckt ein
Codex-Konto ab, das nur eines der beiden Fenster meldet.

Der Glyph wird zentriert in den freien Kern (Ø ~24 px) gezeichnet, in der
gedeckten Track-Farbe, damit die Ringfarben die Aufmerksamkeit behalten.
`severity_color` und die `MIN_SWEEP`-Regel bleiben unverändert.

### `indicator.py` (neu) — `UsageIndicator`

Kapselt genau eine Panel-Anzeige: AppIndicator, Menü, Icon-Dateislots,
Notification-Zustand.

```python
@dataclass(frozen=True)
class IndicatorSpec:
    app_id: str        # "claude-usage-monitor" / "claude-usage-monitor-codex"
    glyph: str         # "C" / "X"
    source: str        # "Claude" / "Codex" — für Titel und Meldungstexte
    label_prefix: str  # "Cl" / "Cx"
```

Beide Indicators teilen sich das Icon-Verzeichnis unter `$XDG_RUNTIME_DIR`,
brauchen aber getrennte Dateinamen, sonst überschreiben sie sich gegenseitig.
Der Basename kommt daher aus dem Spec: `claude-0.png`/`claude-1.png` und
`codex-0.png`/`codex-1.png`. Das Abwechseln zwischen zwei Slots bleibt nötig,
weil das Panel ein Bild nur bei geändertem Dateinamen neu lädt.

Öffentliche Schnittstelle:

- `update(short, long, fetched_at, error, hint)` — zwei `UsageWindow | None`
- `set_active(visible: bool)` — schaltet zwischen `IndicatorStatus.ACTIVE` und
  `PASSIVE`; der Indicator wird nie zerstört, damit das Menü nicht neu aufgebaut
  werden muss und das Panel nicht flackert
- `sync_toggles(show_label, notify)` — spiegelt Checkbox-Zustände, die im
  anderen Menü geändert wurden

Menü-Aktionen (Refresh, Intervall, Panel-Text, Notifications, Beenden) werden
als Callbacks vom Koordinator hereingereicht; der Indicator kennt weder Config
noch Poller.

### `tray.py` — Koordinator

Besitzt `Config`, `Poller`, das `Notify`-Modul und beide Indicators. Verteilt
jeden Snapshot:

| Snapshot-Zustand | Claude-Indicator | Codex-Indicator |
|---|---|---|
| `usage` gesetzt | Ringe + Zeilen | — |
| `usage is None` | Fehler-Icon + Fehlertext (+ Login-Hinweis) | — |
| `codex is None` und `codex_error is None` | — | `PASSIVE` |
| `codex_error` gesetzt | — | `ACTIVE`, Fehler-Icon + Fehlertext |
| `codex` gesetzt | — | `ACTIVE`, Ringe + Zeilen |

Die Sichtbarkeitsregel ist eine freie Funktion in `poller.py` — beim Snapshot,
den sie liest, und damit ohne GTK-Import testbar:

```python
def codex_is_visible(snapshot: Snapshot) -> bool:
    return snapshot.codex is not None or snapshot.codex_error is not None
```

Einstellungen sind bewusst geteilt: eine `Config`, ein `Poller`. Ein Toggle in
einem Menü schreibt die Config und spiegelt sich ins andere Menü; ein
Guard-Flag verhindert, dass das gespiegelte `set_active` erneut das
`toggled`-Signal auslöst. „Beenden" stoppt den Poller und beendet beide Icons.

### `formatting.py`

```python
def format_panel_label(prefix: str, session: float | None, weekly: float | None) -> str
```

Ergebnis `"Cl 80% · 40%"` bzw. `"Cx 20% · 12%"`; ein fehlendes Fenster wird als
`—` gesetzt. Die bisherige Drei-Argument-Form mit angehängtem `| Cx …` entfällt.

## Benachrichtigungen

Vier überwachte Fenster statt zwei. Schwellen (`WARN_THRESHOLD`,
`CRITICAL_THRESHOLD`) und der Menüschalter bleiben unverändert. Der Zustand
„zuletzt gemeldete Stufe" liegt pro Indicator, damit Claude und Codex einander
nicht unterdrücken. Titel: `Claude 5-Stunden-Fenster: 82%`,
`Codex 7-Tage-Fenster: 91%`.

## Fehlerbehandlung

- Icon-Rendering: `OSError`/`MemoryError` → Fallback auf das Theme-Icon
  `dialog-information` (bestehendes Verhalten, jetzt pro Indicator)
- Claude- und Codex-Abruf scheitern weiterhin unabhängig voneinander (Logik im
  Poller, unverändert)
- Fehlt die AppIndicator-Bibliothek, bleibt das bestehende CLI-Fallback-Verhalten

## Tests

Neues `linux/tests/` mit pytest, Marker `unit`:

- `test_formatting.py` — Panel-Label mit beiden Präfixen, fehlende Fenster,
  `format_countdown`-Grenzfälle
- `test_icon.py` — Render-Smoke: `render_rings` und `render_error` schreiben eine
  nicht-leere PNG-Datei; `None`-Werte lösen keine Exception aus
- `test_visibility.py` — `codex_is_visible` für alle vier Snapshot-Zustände

Das GTK-Menü selbst bleibt manueller DBus-Test wie beim ersten Port.

## Nicht im Umfang

- `src/` (Rust, Windows) bleibt unangetastet
- Getrennte Polling-Intervalle pro Quelle
- Konfigurierbare Ring-Reihenfolge oder Farben

## Folgearbeit

`tools/render_demo.py` erzeugt die Demo-Aufnahme aus demselben Zeichencode und
muss auf die neue API umgestellt werden: zwei Icons nebeneinander, beide Labels.
