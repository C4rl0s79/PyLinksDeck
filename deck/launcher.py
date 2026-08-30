"""deck.launcher — uruchamianie gier.

`os.startfile` na pliku `.lnk` wygląda niewinnie, ale oddaje sprawę powłoce
z całym środowiskiem naszego procesu. W wersji spakowanej PyInstallerem to
środowisko jest podmienione (rozpakowany katalog `_MEI` na początku `PATH`,
zmienne Qt wskazujące na *nasze* wtyczki), a DuckStation i PCSX2 też są
aplikacjami Qt — dziedziczą to i mogą nie wstać.

Dlatego uruchamiamy wprost: cel, argumenty i katalog roboczy mamy odczytane ze
skrótu, a proces dostaje środowisko oczyszczone ze śladów PyInstallera i jest
odpięty od nas (`DETACHED_PROCESS`), żeby zamknięcie Decka go nie ubiło.
"""

from __future__ import annotations

import os
import subprocess
import sys

# Zmienne, które PyInstaller albo PySide6 ustawiają pod siebie i które potrafią
# rozstroić inną aplikację Qt.
_DROP = (
    "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_PLATFORM",
    "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_SCALE_FACTOR",
    "QT_SCREEN_SCALE_FACTORS", "QT_AUTO_SCREEN_SCALE_FACTOR",
    "_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE",
    "_PYI_PARENT_PROCESS_LEVEL",
)

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def clean_env() -> dict:
    """Środowisko bez śladów naszego procesu — takie, jakie dostałby program
    uruchomiony z Explorera."""
    env = dict(os.environ)
    for name in _DROP:
        env.pop(name, None)
    home = getattr(sys, "_MEIPASS", "")
    if home:
        low = home.lower()
        parts = [p for p in env.get("PATH", "").split(os.pathsep)
                 if p and low not in p.lower()]
        env["PATH"] = os.pathsep.join(parts)
    return env


def launch(target: str, args: str = "", workdir: str = "",
           lnk: str = "") -> tuple[bool, str]:
    """Uruchamia grę. Zwraca (czy się udało, opis błędu)."""
    if target and os.path.isfile(target):
        # Na Windows przekazujemy gotowy wiersz poleceń — argumenty ze skrótu
        # są już poprawnie cytowane i własne dzielenie tylko by je zepsuło.
        cmd = f'"{target}" {args}'.strip()
        cwd = workdir if workdir and os.path.isdir(workdir) else \
            os.path.dirname(target)
        try:
            subprocess.Popen(
                cmd, cwd=cwd or None, env=clean_env(), close_fds=True,
                creationflags=(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                               | CREATE_BREAKAWAY_FROM_JOB),
            )
            return True, ""
        except OSError as exc:
            return False, f"{type(exc).__name__}: {exc}"

    if lnk:                                   # skrót bez czytelnego celu
        try:
            os.startfile(lnk)
            return True, ""
        except OSError as exc:
            return False, f"{type(exc).__name__}: {exc}"
    return False, "brak celu uruchomienia"


def launch_item(item) -> tuple[bool, str]:
    return launch(item.target, item.args, item.workdir, str(item.lnk))
