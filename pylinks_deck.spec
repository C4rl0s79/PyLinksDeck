# -*- mode: python ; coding: utf-8 -*-
# Budowa przenośnego .exe:  pyinstaller --noconfirm --clean pylinks_deck.spec
# Wynik: dist/PyLinksDeck.exe (portable; ustawienia w %LOCALAPPDATA%\PyLinksDeck).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = collect_submodules("win32com")
hiddenimports += [
    "win32com.client", "win32com.shell",
    "pythoncom", "pywintypes", "win32api", "win32con",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest", "pytest"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PyLinksDeck",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,              # GUI bez okna konsoli
    disable_windowed_traceback=False,
    icon=None,                  # TODO: własna ikona, gdy powstanie
)
