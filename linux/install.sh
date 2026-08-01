#!/usr/bin/env bash
# Installs the Linux tray monitor for the current user.
# No pip, no virtualenv — the package only needs the system Python plus PyGObject.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-/usr/bin/python3}"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/claude-usage-monitor"
AUTOSTART="$HOME/.config/autostart/claude-usage-monitor.desktop"

echo "==> Checking dependencies"
missing=()
"$PYTHON" -c "import gi" 2>/dev/null || missing+=("python3-gi")
"$PYTHON" -c "import cairo" 2>/dev/null || missing+=("python3-gi-cairo")
"$PYTHON" - <<'EOF' 2>/dev/null || missing+=("gir1.2-ayatanaappindicator3-0.1")
import gi
gi.require_version("AyatanaAppIndicator3", "0.1")
import gi.repository.AyatanaAppIndicator3
EOF

if [ ${#missing[@]} -gt 0 ]; then
    echo "Missing system packages: ${missing[*]}"
    echo "Install them with:"
    echo "  sudo apt install ${missing[*]}"
    exit 1
fi

echo "==> Registering package on the Python path"
SITE_DIR="$("$PYTHON" -c 'import site; print(site.getusersitepackages())')"
mkdir -p "$SITE_DIR"
echo "$SOURCE_DIR" > "$SITE_DIR/claude-usage-monitor.pth"

echo "==> Installing launcher into $BIN_DIR"
mkdir -p "$BIN_DIR"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec $PYTHON -m claude_usage_monitor "\$@"
EOF
chmod +x "$LAUNCHER"

echo "==> Installing autostart entry"
mkdir -p "$(dirname "$AUTOSTART")"
cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Code Usage Monitor
Comment=Claude Code and Codex usage windows in the system tray
Exec=$LAUNCHER
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;Monitor;
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF

echo
echo "Done. Verify with:"
echo "  claude-usage-monitor --once"
echo "Start the tray widget with:"
echo "  claude-usage-monitor &"

if ! printf '%s' ":$PATH:" | grep -q ":$BIN_DIR:"; then
    echo
    echo "Note: $BIN_DIR is not on your PATH."
fi
