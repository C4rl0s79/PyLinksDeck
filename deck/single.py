"""deck.single — jedna instancja Decka na sesję użytkownika.

Dwie działające kopie biją się o ten sam profil w `layouts.json` i rysują dwa
docki jeden na drugim. Blokujemy to nazwanym muteksem jądra: pierwsza instancja
go tworzy, każda kolejna dostaje ERROR_ALREADY_EXISTS i kończy pracę.

Mutex nazwany „Local\\..." żyje w sesji logowania, więc nie koliduje z innym
kontem na tym samym komputerze, a system zwalnia go sam, gdy proces zniknie —
także po twardym ubiciu, więc nie zostaje blokada po awarii.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
NAME = "Local\\PyLinksDeck.instance"

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]

_handle = None          # trzymamy uchwyt przy życiu przez czas pracy procesu


def acquire(name: str = NAME) -> bool:
    """True, gdy to jedyna instancja. False, gdy Deck już działa."""
    global _handle
    try:
        _handle = _kernel32.CreateMutexW(None, False, name)
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    except Exception:
        return True         # brak blokady jest lepszy niż brak programu


def show_running() -> bool:
    """Pokazuje dock już działającej instancji (dla użytkownika, który kliknął
    ikonę drugi raz). Zwraca True, gdy udało się znaleźć jej okno."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW(None, "PyLinks Deck — dock")
    if not hwnd:
        return False
    user32.ShowWindow(wintypes.HWND(hwnd), 5)        # SW_SHOW
    return True
