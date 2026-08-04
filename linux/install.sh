#!/usr/bin/env bash
# Installs the Linux tray monitor for the current user.
# No pip, no virtualenv — the package only needs the system Python plus PyGObject.
#
# Typical first-time setup (including an immediate tray launch):
#   ./install.sh --install-deps --start
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-/usr/bin/python3}"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/claude-usage-monitor"
AUTOSTART="$HOME/.config/autostart/claude-usage-monitor.desktop"
INSTALL_DEPS=false
START_AFTER_INSTALL=false

usage() {
    cat <<'EOF'
Usage: ./install.sh [--install-deps] [--start]

  --install-deps  Install missing Debian/Ubuntu AppIndicator dependencies via apt.
  --start         Start the tray monitor after installation.

For a first-time setup, use:
  ./install.sh --install-deps --start
EOF
}

for arg in "$@"; do
    case "$arg" in
        --install-deps) INSTALL_DEPS=true ;;
        --start) START_AFTER_INSTALL=true ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "Unknown option: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

echo "==> Checking dependencies"
missing=()
"$PYTHON" -c "import gi" 2>/dev/null || missing+=("python3-gi")
"$PYTHON" -c "import cairo" 2>/dev/null || missing+=("python3-gi-cairo")
# The tray accepts either binding, so only complain when both are absent.
"$PYTHON" - <<'EOF' 2>/dev/null || missing+=("gir1.2-ayatanaappindicator3-0.1")
import importlib

import gi

for namespace in ("AyatanaAppIndicator3", "AppIndicator3"):
    try:
        gi.require_version(namespace, "0.1")
        importlib.import_module(f"gi.repository.{namespace}")
    except (ValueError, ImportError):
        continue
    break
else:
    raise SystemExit(1)
EOF

if [ ${#missing[@]} -gt 0 ]; then
    if "$INSTALL_DEPS"; then
        if ! command -v apt >/dev/null 2>&1; then
            echo "Missing system packages: ${missing[*]}" >&2
            echo "Automatic installation is currently supported on Debian/Ubuntu only." >&2
            echo "Install the packages with your distribution's package manager and retry." >&2
            exit 1
        fi
        echo "==> Installing system packages: ${missing[*]}"
        sudo apt update
        sudo apt install -y "${missing[@]}"
    else
        echo "Missing system packages: ${missing[*]}"
        echo "Install them with:"
        echo "  sudo apt install ${missing[*]}"
        echo "Or let this script do it:"
        echo "  ./install.sh --install-deps --start"
        exit 1
    fi
fi

echo "==> Registering package on the Python path"
SITE_DIR="$("$PYTHON" -c 'import site; print(site.getusersitepackages())')"
mkdir -p "$SITE_DIR"
echo "$SOURCE_DIR" > "$SITE_DIR/claude-usage-monitor.pth"

echo "==> Installing launcher into $BIN_DIR"
mkdir -p "$BIN_DIR"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$PYTHON" -m claude_usage_monitor "\$@"
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

if "$START_AFTER_INSTALL"; then
    echo "==> Starting tray monitor"
    nohup "$LAUNCHER" >"${XDG_RUNTIME_DIR:-/tmp}/claude-usage-monitor.log" 2>&1 &
    echo "Started (PID $!). Claude and Codex appear as separate tray icons once their CLIs are signed in."
fi
