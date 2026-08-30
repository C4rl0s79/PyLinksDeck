"""deck.ui.launch_fx — efekt uruchomienia gry.

Po dwukliku kafel odrywa się od siatki, rozciąga na cały ekran i gaśnie. To
jedyne potwierdzenie, że kliknięcie zadziałało: emulator albo Steam potrafią
zbierać się kilka sekund, a bez tego pulpit wygląda, jakby nic się nie stało.

Okno efektu nie przyjmuje żadnego wejścia (`WA_TransparentForMouseEvents` plus
`WindowTransparentForInput`), więc nie blokuje pulpitu nawet przez ułamek
sekundy, i kasuje się samo po animacji.
"""

from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup,
                            QPropertyAnimation, QRect, Qt)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

DURATION = 340          # ms — dość, by efekt zauważyć, za mało, by przeszkadzał


class LaunchFlash(QWidget):
    """Kafel rozciągany na pełny ekran i wygaszany."""

    def __init__(self, pixmap: QPixmap, start: QRect, end: QRect) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._pm = pixmap

        self.setGeometry(start)
        self.setWindowOpacity(1.0)
        self.show()

        grow = QPropertyAnimation(self, b"geometry", self)
        grow.setDuration(DURATION)
        grow.setStartValue(start)
        grow.setEndValue(end)
        grow.setEasingCurve(QEasingCurve.OutCubic)

        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(DURATION)
        fade.setStartValue(1.0)
        fade.setKeyValueAt(0.35, 0.75)      # najpierw rośnie, gaśnie pod koniec
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InQuad)

        self._anim = QParallelAnimationGroup(self)
        self._anim.addAnimation(grow)
        self._anim.addAnimation(fade)
        self._anim.finished.connect(self.close)
        self._anim.start()

    def paintEvent(self, ev) -> None:
        if self._pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(self.rect(), self._pm)
        p.end()


def flash(pixmap: QPixmap, start: QRect, screen_rect: QRect) -> LaunchFlash | None:
    """Odpala efekt; zwraca okno, żeby wywołujący trzymał referencję."""
    if pixmap is None or pixmap.isNull() or start.isEmpty():
        return None
    return LaunchFlash(pixmap, start, screen_rect)
