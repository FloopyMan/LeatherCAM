#!/usr/bin/env bash
# Build a portable AppImage from the PyInstaller onedir output.
#
# Prerequisites (Arch / Debian / Fedora — install once):
#   - appimagetool: https://github.com/AppImage/AppImageKit/releases
#     download appimagetool-x86_64.AppImage, chmod +x, drop into PATH
#   - the project's .venv set up via `make dev-install`
#
# Usage:
#   bash packaging/build-appimage.sh
#
# Output: ./dist/LeatherCAM-x86_64.AppImage

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

_resolve_python() {
    if [[ -n "${PYTHON:-}" ]] && (command -v "$PYTHON" >/dev/null 2>&1 || [[ -x "$PYTHON" ]]); then
        printf '%s\n' "$PYTHON"; return 0
    fi
    if [[ -x .venv-dist/bin/python ]]; then
        printf '%s\n' ".venv-dist/bin/python"; return 0
    fi
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then
            printf '%s\n' "$cand"; return 0
        fi
    done
    return 1
}

if ! VENV_PY="$(_resolve_python)"; then
    echo "error: no usable Python found." >&2
    echo "Build with 'make appimage' — it creates an isolated .venv-dist" >&2
    echo "without --system-site-packages, so PyInstaller only sees the" >&2
    echo "runtime dependencies declared in pyproject.toml." >&2
    echo "Or set PYTHON=/path/to/python before invoking this script." >&2
    exit 1
fi
echo "==> using python: $VENV_PY"

if ! command -v appimagetool >/dev/null 2>&1; then
    echo "error: appimagetool not on PATH. Install from:" >&2
    echo "  https://github.com/AppImage/AppImageKit/releases" >&2
    exit 1
fi

echo "==> running PyInstaller (this takes a minute or two)"
rm -rf build dist/leathercam dist/LeatherCAM.AppDir
"$VENV_PY" -m PyInstaller --noconfirm packaging/leathercam.spec

APPDIR="dist/LeatherCAM.AppDir"
echo "==> staging AppDir at $APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r dist/leathercam/* "$APPDIR/usr/bin/"
cp packaging/leathercam.desktop "$APPDIR/usr/share/applications/leathercam.desktop"
cp packaging/leathercam.desktop "$APPDIR/leathercam.desktop"

# Minimal solid-colour icon — replace with a real one before release.
if [[ ! -f packaging/leathercam.png ]]; then
    "$VENV_PY" - <<'PY'
from PIL import Image, ImageDraw
img = Image.new("RGBA", (256, 256), (60, 80, 120, 255))
d = ImageDraw.Draw(img)
d.rectangle((24, 24, 232, 232), outline=(220, 220, 220, 255), width=6)
d.text((70, 110), "LC", fill=(240, 240, 240, 255))
img.save("packaging/leathercam.png")
PY
fi
cp packaging/leathercam.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/leathercam.png"
cp packaging/leathercam.png "$APPDIR/leathercam.png"
ln -sf leathercam.png "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/usr/bin:${LD_LIBRARY_PATH:-}"
exec "$HERE/usr/bin/leathercam" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> building AppImage"
ARCH=x86_64 appimagetool "$APPDIR" "dist/LeatherCAM-x86_64.AppImage"
echo "Done: dist/LeatherCAM-x86_64.AppImage"
