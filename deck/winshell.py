"""deck.winshell — przypięcie okna do pulpitu (WinAPI przez ctypes).

Overlay ma leżeć *na pulpicie*: nad tapetą i ikonami pulpitu, pod zwykłymi
oknami, poza Alt+Tab, bez kradzenia focusu, a mimo to klikalny. Windows nie ma na
to jednego przełącznika, więc mamy trzy tryby:

* ``desktop`` (domyślny) — okno najwyższego poziomu wstawione w kolejności Z tuż
  **nad** warstwę pulpitu (Progman / WorkerW z tapetą). To jedyny wariant, który
  jednocześnie widać i który przyjmuje kliknięcia.
* ``progman`` — próba uczynienia okna dzieckiem powłoki. Windows 11 zwykle
  odmawia (``SetParent`` między procesami), a nawet gdy się uda, okno ląduje pod
  warstwą tapety rysowaną przez WorkerW. Zostawione jako furtka.
* ``bottom`` — dno kolejności Z. UWAGA: to znaczy dno *pod pulpitem*, więc tapeta
  i ikony pulpitu zasłaniają overlay. Przydatne wyłącznie do diagnostyki.

Explorer bywa restartowany (albo pada) — wtedy Progman powstaje na nowo i
przypięcie trzeba powtórzyć. Służy do tego komunikat ``TaskbarCreated``,
który powłoka rozgłasza po odrodzeniu.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

HWND_TOP = 0
HWND_BOTTOM = 1
GW_HWNDNEXT = 2
GW_HWNDPREV = 3
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

SMTO_NORMAL = 0x0000

user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.restype = wintypes.HWND
user32.GetParent.restype = wintypes.HWND
user32.GetTopWindow.restype = wintypes.HWND
user32.GetWindow.restype = wintypes.HWND
user32.SetParent.restype = wintypes.HWND


def _get_long(hwnd: int, idx: int) -> int:
    fn = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    fn.restype = ctypes.c_ssize_t
    return int(fn(wintypes.HWND(hwnd), idx))


def _set_long(hwnd: int, idx: int, value: int) -> int:
    fn = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
    fn.restype = ctypes.c_ssize_t
    fn.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    return int(fn(wintypes.HWND(hwnd), idx, value))


def taskbar_created_message() -> int:
    """ID komunikatu rozgłaszanego przez powłokę po (ponownym) starcie."""
    return int(user32.RegisterWindowMessageW("TaskbarCreated"))


def find_progman() -> int:
    return int(user32.FindWindowW("Progman", None) or 0)


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def desktop_layer() -> int:
    """Najwyższe w kolejności Z okno warstwy pulpitu (Progman albo WorkerW).

    Tapeta bywa rysowana przez Progman, a bywa przez osobne WorkerW — zależnie od
    tego, czy powłoka włączyła przejścia tła. Interesuje nas to, które z nich leży
    najwyżej, bo dopiero nad nim overlay jest widoczny.
    """
    hwnd = int(user32.GetTopWindow(None) or 0)
    while hwnd:
        if _class_name(hwnd) in ("Progman", "WorkerW") and user32.IsWindowVisible(
                wintypes.HWND(hwnd)):
            return hwnd
        hwnd = int(user32.GetWindow(wintypes.HWND(hwnd), GW_HWNDNEXT) or 0)
    return find_progman()


def pin_above_desktop(hwnd: int) -> bool:
    """Wstawia okno tuż nad warstwę pulpitu, pod wszystkie zwykłe okna.

    Robimy to, wstawiając się bezpośrednio pod oknem, które leży nad pulpitem —
    dzięki temu overlay nie przykrywa niczego, co użytkownik ma otwarte, ale sam
    nie ginie pod tapetą (to była pułapka wariantu HWND_BOTTOM).
    """
    layer = desktop_layer()
    if not layer:
        return False
    above = int(user32.GetWindow(wintypes.HWND(layer), GW_HWNDPREV) or 0)
    if above == hwnd:                       # już jesteśmy tuż nad pulpitem
        return True
    target = above if above else HWND_TOP
    return bool(user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(target),
                                    0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))


def is_below_desktop(hwnd: int) -> bool:
    """Czy warstwa pulpitu leży NAD naszym oknem (czyli nas zasłania).

    Explorer potrafi podnieść pulpit — np. po kliknięciu w tapetę albo po
    „Pokaż pulpit" — i wtedy overlay znika z oczu, choć nadal jest widoczny dla
    systemu. Sprawdzenie jest tanie: schodzimy kolejnością Z i patrzymy, co
    napotkamy pierwsze.
    """
    cur = int(user32.GetTopWindow(None) or 0)
    while cur:
        if cur == hwnd:
            return False
        if _class_name(cur) in ("Progman", "WorkerW") and user32.IsWindowVisible(
                wintypes.HWND(cur)):
            return True
        cur = int(user32.GetWindow(wintypes.HWND(cur), GW_HWNDNEXT) or 0)
    return False


HWND_TOPMOST = -1
HWND_NOTOPMOST = -2


def set_topmost(hwnd: int, on: bool) -> None:
    """Wymusza (albo zdejmuje) status okna zawsze na wierzchu."""
    target = HWND_TOPMOST if on else HWND_NOTOPMOST
    user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(target), 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def make_unobtrusive(hwnd: int) -> None:
    """Bez focusu, bez Alt+Tab, bez przycisku na pasku zadań."""
    ex = _get_long(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    ex &= ~WS_EX_APPWINDOW
    _set_long(hwnd, GWL_EXSTYLE, ex)


def send_to_bottom(hwnd: int) -> None:
    user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(HWND_BOTTOM),
                        0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def attach_to_progman(hwnd: int) -> bool:
    """Czyni okno dzieckiem powłoki. Zwraca True, gdy się udało."""
    pm = find_progman()
    if not pm:
        return False
    prev = user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(pm))
    return bool(prev) or user32.GetParent(wintypes.HWND(hwnd)) == pm


def detach(hwnd: int) -> None:
    """Odpina okno od powłoki (np. przed zamknięciem albo zmianą trybu)."""
    try:
        user32.SetParent(wintypes.HWND(hwnd), None)
    except Exception:
        pass


def is_child_of_shell(hwnd: int) -> bool:
    pm = find_progman()
    return bool(pm) and int(user32.GetParent(wintypes.HWND(hwnd)) or 0) == pm


def screen_to_parent(hwnd: int, x: int, y: int) -> tuple[int, int]:
    """Przelicza punkt ekranowy na układ współrzędnych rodzica okna.

    Gdy okno wisi pod Progman, jego (0,0) nie jest lewym górnym rogiem pulpitu,
    więc pozycję z Qt trzeba przetłumaczyć — inaczej overlay ląduje obok.
    """
    parent = int(user32.GetParent(wintypes.HWND(hwnd)) or 0)
    if not parent:
        return x, y
    pt = wintypes.POINT(x, y)
    if user32.ScreenToClient(wintypes.HWND(parent), ctypes.byref(pt)):
        return int(pt.x), int(pt.y)
    return x, y
