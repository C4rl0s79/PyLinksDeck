"""deck.ui.dock — belka zakładek u góry pulpitu.

Dock jest jedyną rzeczą, którą Deck trzyma na widoku na stałe. Każda grupa to
jedna zakładka; szerokość zakładki wynika wprost z szerokości docka podzielonej
przez liczbę widocznych grup, więc belka zawsze jest wypełniona równo i nie
zależy od długości nazw.

Najechanie myszą rozwija panel z kaflami, kliknięcie przełącza grupę, kółko
przewija zakładki, prawy przycisk otwiera opcje. Zakładka pokazuje logotyp
platformy, jeśli jest dostępny i włączony — inaczej nazwę.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from deck.logos import LogoSet
from deck.profiles import Group


class DockBar(QWidget):
    """Belka zakładek — zawsze widoczna warstwa sterująca Deckiem."""

    activated = Signal(str)             # gid klikniętej zakładki
    hovered = Signal(str)               # gid zakładki pod kursorem (rozwija panel)
    exited = Signal()
    options_requested = Signal(QPoint)

    def __init__(self, logos: LogoSet, parent=None) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("PyLinks Deck — dock")

        self.logos = logos
        self.groups: list[Group] = []
        self.active_gid = ""
        self.show_logos = True
        self._hover = -1

    # ── stan ──────────────────────────────────────────────────────────────
    def set_groups(self, groups: list[Group], active_gid: str) -> None:
        self.groups = groups
        self.active_gid = active_gid
        self._hover = -1
        self.update()

    def set_active(self, gid: str) -> None:
        if gid != self.active_gid:
            self.active_gid = gid
            self.update()

    def set_show_logos(self, on: bool) -> None:
        self.show_logos = on
        self.update()

    # ── geometria zakładek ────────────────────────────────────────────────
    def tab_width(self) -> float:
        n = max(1, len(self.groups))
        return self.width() / n

    def tab_rect(self, i: int) -> QRect:
        w = self.tab_width()
        return QRect(int(i * w), 0, int(w) + 1, self.height())

    def index_at(self, x: int) -> int:
        if not self.groups:
            return -1
        i = int(x / max(1.0, self.tab_width()))
        return i if 0 <= i < len(self.groups) else -1

    # ── rysowanie ─────────────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        radius = min(14, self.height() // 3)
        p.setBrush(QColor(16, 17, 21, 225))
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)

        if not self.groups:
            p.setPen(QColor(220, 220, 230, 160))
            p.drawText(self.rect(), Qt.AlignCenter, "brak grup — prawy klik, aby dodać")
            p.end()
            return

        dpr = float(self.devicePixelRatioF())
        f = QFont(self.font())
        f.setPixelSize(max(11, int(self.height() * 0.34)))
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)

        for i, g in enumerate(self.groups):
            r = self.tab_rect(i)
            active = g.gid == self.active_gid
            if active:
                p.setBrush(QColor(255, 255, 255, 26))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(r.adjusted(3, 4, -3, -4), 8, 8)
            elif i == self._hover:
                p.setBrush(QColor(255, 255, 255, 14))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(r.adjusted(3, 4, -3, -4), 8, 8)

            logo = None
            if self.show_logos and g.platform:
                logo = self.logos.fitted(g.logo or g.platform, r.width() - 16,
                                         int(self.height() * 0.62), dpr)
            lh = logo.height() / max(1.0, dpr) if logo is not None else 0
            if logo is not None and lh >= 11:     # niżej logotyp jest nieczytelny
                lw = logo.width() / max(1.0, dpr)
                lx = int(r.center().x() - lw / 2)
                ly = int(r.center().y() - lh / 2)
                if self.logos.is_dark(g.logo or g.platform):
                    p.setBrush(QColor(238, 238, 244, 235))
                    p.setPen(Qt.NoPen)
                    p.drawRoundedRect(lx - 6, ly - 4, int(lw) + 12, int(lh) + 8, 5, 5)
                p.drawPixmap(lx, ly, int(lw), int(lh), logo)
            else:
                p.setPen(QColor(245, 245, 250) if active
                         else QColor(215, 218, 228, 210))
                p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignCenter,
                           fm.elidedText(g.title, Qt.ElideRight, r.width() - 12))

            if active:                       # podkreślenie aktywnej zakładki
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(96, 156, 255, 230))
                p.drawRoundedRect(r.x() + 10, r.bottom() - 4,
                                  max(12, r.width() - 20), 3, 2, 2)
        p.end()

    # ── mysz ──────────────────────────────────────────────────────────────
    def enterEvent(self, ev) -> None:
        super().enterEvent(ev)
        self.hovered.emit(self.active_gid)

    def leaveEvent(self, ev) -> None:
        super().leaveEvent(ev)
        self._hover = -1
        self.update()
        self.exited.emit()

    def mouseMoveEvent(self, ev) -> None:
        i = self.index_at(ev.position().toPoint().x())
        if i != self._hover:
            self._hover = i
            self.update()
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev) -> None:
        i = self.index_at(ev.position().toPoint().x())
        if ev.button() == Qt.RightButton:
            self.options_requested.emit(ev.globalPosition().toPoint())
            ev.accept()
            return
        if ev.button() == Qt.LeftButton and 0 <= i < len(self.groups):
            self.activated.emit(self.groups[i].gid)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def wheelEvent(self, ev) -> None:
        """Kółko nad dockiem przerzuca zakładki — szybciej niż celowanie myszą."""
        if not self.groups:
            return
        gids = [g.gid for g in self.groups]
        try:
            cur = gids.index(self.active_gid)
        except ValueError:
            cur = 0
        cur = (cur + (-1 if ev.angleDelta().y() > 0 else 1)) % len(gids)
        self.activated.emit(gids[cur])
        ev.accept()
