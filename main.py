"""PyLinks Deck — ikony gier na pulpicie, rysowane po naszemu.

Uruchomienie: python main.py
Na pulpicie zostaje belka zakładek; najechanie na nią rozwija panel z kaflami.

Tryb kontrolny: python main.py --shot podglad.png [sekundy]
Renderuje dock i rozwinięty panel do pliku i kończy pracę — pozwala sprawdzić
sam rysunek, bez szukania odsłoniętego pulpitu.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QApplication


def _shot(app_deck, path: str, delay_ms: int) -> None:
    """Zapisuje dock i panel na wspólnym tle (kafle liczą się w tle)."""
    def grab() -> None:
        dock, panel = app_deck.dock, app_deck.panel
        area = dock.geometry().united(panel.geometry())
        pm = QPixmap(area.size())
        pm.fill(QColor(32, 34, 40))
        p = QPainter(pm)
        for w in (panel, dock):
            if w.isVisible():
                w.render(p, w.geometry().topLeft() - area.topLeft())
        p.end()
        pm.save(path)
        print(f"zapisano {path} ({pm.width()}x{pm.height()})")
        QApplication.quit()

    QTimer.singleShot(delay_ms, grab)


def main() -> int:
    # PassThrough zamiast zaokrąglania skali: na laptopie 2560×1600 przy 150 %
    # zaokrąglenie do 2× robiłoby dokładnie to, na co cierpi pulpit Windows —
    # rozjazd rozmiarów przy przepięciu ekranu.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("PyLinks Deck")
    app.setQuitOnLastWindowClosed(False)

    from deck.ui.deck_app import DeckApp

    deck = DeckApp()

    if "--shot" in sys.argv:
        i = sys.argv.index("--shot")
        path = sys.argv[i + 1] if len(sys.argv) > i + 1 else "deck.png"
        secs = float(sys.argv[i + 2]) if len(sys.argv) > i + 2 else 6.0
        deck._show_panel()
        _shot(deck, path, int(secs * 1000))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
