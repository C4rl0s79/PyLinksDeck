"""deck.autostart — uruchamianie Decka razem z Windows.

Wpis idzie do klucza użytkownika (HKCU\\...\\Run), nie do gałęzi maszyny: nie
wymaga uprawnień administratora i dotyczy wyłącznie tego konta. Uruchamiamy
przez ``pythonw.exe``, żeby przy starcie systemu nie mrugało okno konsoli.
"""

from __future__ import annotations

import sys
from pathlib import Path

import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "PyLinksDeck"


def _pythonw() -> str:
    """Interpreter bez konsoli, jeśli istnieje obok bieżącego."""
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        cand = exe.with_name("pythonw.exe")
        if cand.is_file():
            return str(cand)
    return str(exe)


def command() -> str:
    """Komenda zapisywana w rejestrze — ta sama, którą uruchomiono program."""
    if getattr(sys, "frozen", False):          # spakowany .exe
        return f'"{sys.executable}"'
    # Ścieżkę liczymy z położenia pakietu, nie z sys.argv[0] — ten ostatni bywa
    # "-c" albo ścieżką względną, zależnie od sposobu uruchomienia.
    script = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{_pythonw()}" "{script}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, VALUE)
            return bool(value)
    except OSError:
        return False


def current_command() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, VALUE)
            return str(value)
    except OSError:
        return ""


def enable() -> bool:
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, command())
        return True
    except OSError:
        return False


def disable() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, VALUE)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(on: bool) -> bool:
    return enable() if on else disable()


def refresh_if_enabled() -> None:
    """Aktualizuje wpis, gdy zmieniła się ścieżka programu (np. po przeniesieniu)."""
    if is_enabled() and current_command() != command():
        enable()
