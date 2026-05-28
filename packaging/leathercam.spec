# PyInstaller spec for LeatherCAM.
#
# Build with:
#   pyinstaller packaging/leathercam.spec
#
# Output layout:
#   dist/leathercam/leathercam(.exe)  — main executable
#   dist/leathercam/_internal/         — Python runtime + libs
#
# Single-file mode is intentionally not used: PySide6 + OpenCV + Shapely
# unpack to a tempdir on every launch, which adds 3–5 seconds. onedir
# starts in well under a second and ships the same total bytes.

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# PySide6's stock hook can miss the actual Qt6*.dll binaries on Windows,
# producing "DLL load failed while importing QtWidgets" at first launch.
# collect_all walks the package and grabs every .pyd, .dll and resource.
pyside_datas, pyside_binaries, pyside_hidden = collect_all("PySide6")
shiboken_datas, shiboken_binaries, shiboken_hidden = collect_all("shiboken6")

hidden = list(pyside_hidden) + list(shiboken_hidden)
hidden += collect_submodules("svgelements")
hidden += collect_submodules("ezdxf")
hidden += collect_submodules("shapely")
hidden += collect_submodules("pyclipper")
hidden += collect_submodules("scipy.ndimage")

datas = list(pyside_datas) + list(shiboken_datas)
datas += collect_data_files("ezdxf")

binaries = list(pyside_binaries) + list(shiboken_binaries)

a = Analysis(
    ["../leathercam/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib.tests",
        "pytest",
        "PIL.ImageQt",
        # We use PySide6; if the build host has PyQt5/PyQt6/PySide2 in
        # site-packages, PyInstaller refuses to bundle multiple Qt bindings.
        "PyQt5",
        "PyQt6",
        "PySide2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="leathercam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="leathercam",
)
