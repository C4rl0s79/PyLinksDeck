"""deck.ui.panel — panel z kaflami rozwijany pod dockiem.

Panel zajmuje prawie cały pulpit i pokazuje zawartość jednej grupy — tej
wybranej w docku. Pojawia się po najechaniu na dock, znika po zjechaniu myszą
(chyba że wyłączysz autoukrywanie). Nie ma tu ramek do przeciągania: rozmiar i
położenie wynikają z profilu ekranu, a jedyne, co się skaluje, to kafle.
"""

from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                            QSize, Qt, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from deck.library import Item
from deck.profiles import Group, clamp_cols
from deck.thumbs import ASPECTS, ThumbCache
from deck.ui.tiles import GAP, TileView

GRIP = 12          # wysokość strefy chwytania przy dolnej krawędzi
OPEN_MS = 210      # rozwijanie — trochę wolniej, bo to ruch „do przodu"
CLOSE_MS = 160     # zwijanie — szybciej, żeby nie zawadzało


class PanelWindow(QWidget):
    """Rozwijana tafla z kaflami jednej grupy."""

    entered = Signal()
    exited = Signal()
    cols_changed = Signal(str, int)          # gid, nowa liczba kolumn
    height_changed = Signal(int)             # nowy zasięg panelu w px
    launched = Signal(object, QRect, QPixmap)  # gra uruchomiona z kafla
    context_requested = Signal(object, QPoint)  # prawy klik na kaflu

    def __init__(self, cache: ThumbCache, parent=None) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("PyLinks Deck — panel")

        self.group: Group | None = None
        self.dpr = 1.0
        self.show_labels = True
        self._resize_from: tuple[int, int] | None = None

        self.title = QLabel("", self)
        self.title.setStyleSheet("color:#f2f2f7; font-weight:600;")
        self.count = QLabel("", self)
        self.count.setStyleSheet("color:rgba(242,242,247,130);")
        self.hint = QLabel("Ctrl + kółko — rozmiar kafli · dwuklik — uruchom", self)
        self.hint.setStyleSheet("color:rgba(242,242,247,90);")

        head = QHBoxLayout()
        head.setContentsMargins(18, 10, 18, 4)
        head.setSpacing(10)
        head.addWidget(self.title)
        head.addWidget(self.count)
        head.addStretch(1)
        head.addWidget(self.hint)

        self.view = TileView(cache, self)
        self.view.zoom_step = self._zoom_step          # skalowanie idzie do profilu
        self.view.launched.connect(self.launched)
        self.view.context_requested.connect(self.context_requested)

        # Rozwijanie i zwijanie: animujemy geometrię okna, więc panel „wysuwa
        # się" spod docka zamiast pojawiać się skokiem.
        self._slide = QPropertyAnimation(self, b"geometry", self)
        self._target = QRect()
        self._closing = False
        self._slide.finished.connect(self._on_slide_done)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, GRIP + 6)      # miejsce na uchwyt
        lay.setSpacing(2)
        lay.addLayout(head)
        lay.addWidget(self.view, 1)

    # ── zawartość ─────────────────────────────────────────────────────────
    def set_group(self, group: Group, items: list[Item], dpr: float,
                  show_labels: bool, spine_ok: bool = False) -> None:
        self.group, self.dpr, self.show_labels = group, dpr, show_labels
        m = self.view.model_
        m.fit_mode = group.fit_mode
        m.spine_ok = spine_ok
        self.title.setText(group.title)
        self.count.setText(str(len(items)))
        self.view.model_.set_items(items)
        self._apply_tile()
        self.view.scrollToTop()

    # ── rozwijanie i zwijanie ─────────────────────────────────────────────
    def reveal(self, rect: QRect, animate: bool = True) -> None:
        """Pokazuje panel w zadanej geometrii, wysuwając go spod docka."""
        self._target = QRect(rect)
        self._closing = False
        self._slide.stop()
        if self.isVisible():
            if animate and self.geometry() != rect:
                self._run(rect, CLOSE_MS, QEasingCurve.OutCubic)
            else:
                self.setGeometry(rect)
            return
        if not animate:
            self.setGeometry(rect)
            self.show()
            return
        self.setGeometry(QRect(rect.x(), rect.y(), rect.width(), 2))
        self.show()
        self._run(rect, OPEN_MS, QEasingCurve.OutCubic)

    def dismiss(self, animate: bool = True) -> None:
        """Zwija panel z powrotem pod dock."""
        if not self.isVisible():
            return
        self._slide.stop()
        if not animate:
            self.hide()
            return
        self._closing = True
        collapsed = QRect(self.x(), self.y(), self.width(), 2)
        self._run(collapsed, CLOSE_MS, QEasingCurve.InCubic)

    def _run(self, end: QRect, ms: int, curve) -> None:
        # Sygnał podpinamy raz w konstruktorze — o tym, czy po animacji schować
        # okno, decyduje flaga `_closing`, nie przepinanie połączeń.
        self._slide.setDuration(ms)
        self._slide.setStartValue(self.geometry())
        self._slide.setEndValue(end)
        self._slide.setEasingCurve(curve)
        self._slide.start()

    def _on_slide_done(self) -> None:
        if self._closing:
            self._closing = False
            self.hide()
            if not self._target.isNull():        # wróć do pełnej wysokości
                self.setGeometry(self._target)

    def set_scroll_speed(self, value: float) -> None:
        self.view.scroll_speed = value

    def _apply_tile(self) -> None:
        if self.group is None:
            return
        ratio = ASPECTS.get(self.group.aspect, 1.5)
        self.view.set_tile(self.group.cols, ratio, self.show_labels, self.dpr)

    def content_height(self, width: int) -> int:
        """Wysokość potrzebna, by pokazać całą grupę przy danej szerokości.

        Trzy gry nie mają powodu rozpychać panelu na 80 % ekranu — panel rośnie
        do zawartości, a dopiero potem obcina go limit z profilu.
        """
        if self.group is None:
            return 260
        # ta sama arytmetyka co układ siatki — inaczej panel byłby za wysoki
        # albo obcinał ostatni wiersz
        rows = self.view.row_heights(width - 20)   # wiersze z zawiniętymi tytułami
        if not rows:
            _, _, tile_h = self.view.metrics(width - 20)
            rows = [tile_h + GAP]
        return 34 + sum(rows) + 24                    # nagłówek + siatka + margines

    def _zoom_step(self, step: int) -> None:
        """Kółko w górę = mniej kolumn, czyli większe kafle."""
        if self.group is None:
            return
        self.group.cols = clamp_cols(self.group.cols - step)
        self._apply_tile()
        self.cols_changed.emit(self.group.gid, self.group.cols)

    # ── tło i uchwyt ──────────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QColor(14, 15, 19, 232))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)

        # Uchwyt: sygnał, że dolną krawędź można pociągnąć.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 70))
        w = max(40, self.width() // 12)
        p.drawRoundedRect(int((self.width() - w) / 2), self.height() - GRIP + 3,
                          w, 3, 2, 2)
        p.end()

    # ── mysz ──────────────────────────────────────────────────────────────
    def _in_grip(self, pos) -> bool:
        return pos.y() >= self.height() - GRIP

    def mouseMoveEvent(self, ev) -> None:
        pos = ev.position().toPoint()
        if self._resize_from is not None:
            start_y, start_h = self._resize_from
            delta = ev.globalPosition().toPoint().y() - start_y
            self.setFixedHeight(max(160, start_h + delta))
            self.resize(self.width(), max(160, start_h + delta))
            ev.accept()
            return
        self.setCursor(Qt.SizeVerCursor if self._in_grip(pos) else Qt.ArrowCursor)
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton and self._in_grip(ev.position().toPoint()):
            self._resize_from = (ev.globalPosition().toPoint().y(), self.height())
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if self._resize_from is not None:
            self._resize_from = None
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)          # zdejmij blokadę z setFixedHeight
            self.height_changed.emit(self.height())
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def enterEvent(self, ev) -> None:
        super().enterEvent(ev)
        self.entered.emit()

    def leaveEvent(self, ev) -> None:
        super().leaveEvent(ev)
        self.setCursor(Qt.ArrowCursor)
        self.exited.emit()
