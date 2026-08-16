# PyInstaller spec for Papyrik -> dist/Papyrik.exe (one-file, windowed).
#
# Build:  pyinstaller papyrik.spec
#
# The heavy PDF/imaging deps ship data files and dynamically imported
# submodules that PyInstaller can miss, so we collect them explicitly.

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

for pkg in ("pymupdf", "fitz", "pdf2docx"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# cryptography (pypdf AES) pulls native backends in dynamically.
hiddenimports += collect_submodules("cryptography")

a = Analysis(
    ["run_papyrik.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Papyrik",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # windowed GUI app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
